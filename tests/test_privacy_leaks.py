# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline leak tests: with a proxy set, nothing may reach trackers, peers or DHT nodes directly.

Every target is a loopback sentinel; the proxy is a dead endpoint (or a SOCKS5 proxy that refuses UDP) that only
records attempts. A positive control without a proxy proves the sentinels can see traffic, so "nothing received"
really means "nothing sent". Nothing in these tests leaves the machine.
"""

import os
import socket
import struct
import sys
import time
from contextlib import ExitStack

import libtorrent as lt
import pytest

from meerko_bittorent.engine import Engine
from meerko_bittorent.proxy import ProxyKind, ProxySettings
from tests.sentinels import LOOPBACK, SOCKS5_UDP_ASSOCIATE, Socks5NoUdpProxy, TcpSentinel, UdpSentinel

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="loopback leak tests run on Linux")

POSITIVE_CONTROL_SECONDS = 10.0
LEAK_WINDOW_SECONDS = 8.0
UTP_REPLY_WAIT_SECONDS = 3.0
UTP_SYN_TYPE_AND_VERSION = 0x41  # ST_SYN (4) << 4 | version 1

# Test-session settings: announce to every tracker at once, so every leak path is exercised inside the window
STRICTER_ANNOUNCES = {"announce_to_all_tiers": True, "announce_to_all_trackers": True}
# Direct mode would otherwise reach the real network (router ports, LAN broadcast, the public DHT bootstrap host)
KEEP_DIRECT_MODE_OFFLINE = {"enable_upnp": False, "enable_natpmp": False, "enable_lsd": False, "dht_bootstrap_nodes": ""}


# Start the leak targets plus the given proxy sentinel; returns them by role
def start_sentinels(stack: ExitStack, proxy_sentinel: TcpSentinel) -> dict:
    roles = {
        "http_tracker": TcpSentinel("HTTP tracker"),
        "udp_tracker": UdpSentinel("UDP tracker"),
        "peer": TcpSentinel("peer"),
        "dht_node": UdpSentinel("DHT node"),
        "proxy": proxy_sentinel,
    }
    # Each sentinel serves until the stack closes
    for sentinel in roles.values():
        stack.enter_context(sentinel)
    return roles


# A torrent whose data is absent (so it wants peers) announcing to both tracker sentinels
def write_torrent(directory, sentinels) -> str:
    payload = directory / "payload.bin"
    payload.write_bytes(os.urandom(64 * 1024))
    file_storage = lt.file_storage()
    lt.add_files(file_storage, str(payload))
    creator = lt.create_torrent(file_storage)
    creator.add_tracker(f"http://{LOOPBACK}:{sentinels['http_tracker'].port}/announce", 0)
    creator.add_tracker(f"udp://{LOOPBACK}:{sentinels['udp_tracker'].port}/announce", 1)
    lt.set_piece_hashes(creator, str(directory))
    payload.unlink()
    torrent_path = directory / "leak.torrent"
    torrent_path.write_bytes(lt.bencode(creator.generate()))
    return str(torrent_path)


# Run Meerko against the sentinels (proxy_kind None = direct); returns (sentinels, engine, download)
def start_scenario(stack: ExitStack, tmp_path, proxy_kind: ProxyKind | None, proxy_sentinel=None, listen_port=0):
    sentinels = start_sentinels(stack, proxy_sentinel or TcpSentinel("dead proxy"))
    proxy = None
    # Point the proxy at its sentinel so any proxied traffic is visible but goes nowhere
    if proxy_kind is not None:
        proxy = ProxySettings(proxy_kind, LOOPBACK, sentinels["proxy"].port)
    engine = Engine(proxy, listen_interfaces=f"{LOOPBACK}:{listen_port}", lock_directory=tmp_path / "locks")
    stack.callback(engine.close)
    engine.session.apply_settings(STRICTER_ANNOUNCES)
    # Only direct mode needs taming; proxy modes are already offline by policy and must be tested as shipped
    if proxy_kind is None:
        engine.session.apply_settings(KEEP_DIRECT_MODE_OFFLINE)
    download = engine.start(write_torrent(tmp_path, sentinels), tmp_path)
    stack.callback(download.close)
    # Give libtorrent a DHT node and a peer to talk to, the way it would learn them from the swarm
    engine.session.add_dht_node((LOOPBACK, sentinels["dht_node"].port))
    download.handle.connect_peer((LOOPBACK, sentinels["peer"].port))
    return sentinels, engine, download


# Names of the leak targets (everything except the proxy) that were contacted
def contacted_targets(sentinels: dict) -> list[str]:
    return [sentinel.name for role, sentinel in sentinels.items() if role != "proxy" and sentinel.contacts]


# A free loopback port number (TCP and UDP), so the incoming test knows where Meerko would listen
def free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((LOOPBACK, 0))
        return probe.getsockname()[1]


# Send a uTP connection request (ST_SYN) to the port; True if anything answers
def utp_answers(port: int) -> bool:
    syn = struct.pack(">BBHIIIHH", UTP_SYN_TYPE_AND_VERSION, 0, 4242, 1, 0, 1 << 20, 1, 0)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.settimeout(UTP_REPLY_WAIT_SECONDS)
        client.sendto(syn, (LOOPBACK, port))
        try:
            client.recvfrom(1500)
        except (socket.timeout, ConnectionRefusedError):
            return False
    return True


# Without a proxy every sentinel is reached: the harness can see traffic
def test_positive_control_reaches_all_sentinels(tmp_path):
    with ExitStack() as stack:
        sentinels, _engine, _download = start_scenario(stack, tmp_path, None)
        deadline = time.monotonic() + POSITIVE_CONTROL_SECONDS
        targets = [sentinel for role, sentinel in sentinels.items() if role != "proxy"]
        # Wait for each target in turn, sharing one deadline
        for sentinel in targets:
            sentinel.contacted.wait(max(0.0, deadline - time.monotonic()))
        assert sorted(contacted_targets(sentinels)) == sorted(sentinel.name for sentinel in targets)


# SOCKS5 strict mode: no direct contact at all, and the proxy really was used
def test_socks5_dead_proxy_leaks_nothing(tmp_path):
    with ExitStack() as stack:
        sentinels, _engine, _download = start_scenario(stack, tmp_path, ProxyKind.SOCKS5)
        time.sleep(LEAK_WINDOW_SECONDS)
        assert contacted_targets(sentinels) == []
        assert sentinels["proxy"].contacts >= 1


# A live SOCKS5 proxy that refuses UDP: DHT, uTP and UDP trackers must fail, never go direct (review I4)
def test_socks5_without_udp_support_leaks_nothing(tmp_path):
    with ExitStack() as stack:
        proxy = Socks5NoUdpProxy()
        sentinels, _engine, _download = start_scenario(stack, tmp_path, ProxyKind.SOCKS5, proxy_sentinel=proxy)
        time.sleep(LEAK_WINDOW_SECONDS)
        assert contacted_targets(sentinels) == []
        assert SOCKS5_UDP_ASSOCIATE in proxy.commands


# HTTP strict mode: no direct contact, no UDP tracker left, no DHT
def test_http_dead_proxy_leaks_nothing(tmp_path):
    with ExitStack() as stack:
        sentinels, engine, download = start_scenario(stack, tmp_path, ProxyKind.HTTP)
        time.sleep(LEAK_WINDOW_SECONDS)
        assert contacted_targets(sentinels) == []
        assert sentinels["proxy"].contacts >= 1
        assert not [entry["url"] for entry in download.handle.trackers() if entry["url"].startswith("udp://")]
        assert engine.session.get_settings()["enable_dht"] is False


# With a proxy there is no TCP listener and the UDP socket ignores direct uTP; the direct control shows both work
@pytest.mark.parametrize("proxy_kind", [None, ProxyKind.SOCKS5, ProxyKind.HTTP])
def test_incoming_connections_refused_with_proxy(tmp_path, proxy_kind):
    port = free_loopback_port()
    with ExitStack() as stack:
        _sentinels, engine, _download = start_scenario(stack, tmp_path, proxy_kind, listen_port=port)
        time.sleep(1)
        # Control: without a proxy Meerko listens on the port and answers uTP, so the checks below can fail
        if proxy_kind is None:
            assert engine.listen_port == port
            assert utp_answers(port) is True
            return
        assert engine.listen_port == 0
        with pytest.raises(ConnectionRefusedError):
            socket.create_connection((LOOPBACK, port), timeout=UTP_REPLY_WAIT_SECONDS).close()
        assert utp_answers(port) is False
