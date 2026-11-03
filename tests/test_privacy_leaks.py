# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline leak tests: with a proxy set, nothing may reach trackers, peers or DHT nodes directly.

Every target is a loopback sentinel; the proxy is a dead endpoint that only records attempts. A positive control
without a proxy proves the sentinels can see traffic, so "nothing received" really means "nothing sent".
"""

import os
import socket
import sys
import time
from contextlib import ExitStack

import libtorrent as lt
import pytest

from meerko_bittorent.engine import Engine
from meerko_bittorent.proxy import ProxyKind, ProxySettings
from tests.sentinels import LOOPBACK, TcpSentinel, UdpSentinel

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="loopback leak tests run on Linux")

POSITIVE_CONTROL_SECONDS = 10.0
LEAK_WINDOW_SECONDS = 8.0
HANDSHAKE_WAIT_SECONDS = 5.0


# Start every sentinel plus the dead proxy; returns them by role
def start_sentinels(stack: ExitStack) -> dict:
    roles = {
        "http_tracker": TcpSentinel("HTTP tracker"),
        "udp_tracker": UdpSentinel("UDP tracker"),
        "peer": TcpSentinel("peer"),
        "dht_node": UdpSentinel("DHT node"),
        "dead_proxy": TcpSentinel("dead proxy"),
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


# Run Meerko against the sentinels with the given proxy kind (None = direct); returns (sentinels, engine, download)
def start_scenario(stack: ExitStack, tmp_path, proxy_kind: ProxyKind | None):
    sentinels = start_sentinels(stack)
    proxy = None
    # Point the proxy at the dead endpoint so any proxied traffic is visible but goes nowhere
    if proxy_kind is not None:
        proxy = ProxySettings(proxy_kind, LOOPBACK, sentinels["dead_proxy"].port)
    engine = Engine(proxy, listen_interfaces=f"{LOOPBACK}:0", lock_directory=tmp_path / "locks")
    stack.callback(engine.close)
    # Announce to every tracker at once (normally only the first tier until it fails): every possible leak path
    # is exercised inside the test window, which makes these tests stricter, not looser
    engine.session.apply_settings({"announce_to_all_tiers": True, "announce_to_all_trackers": True})
    download = engine.start(write_torrent(tmp_path, sentinels), tmp_path)
    stack.callback(download.close)
    # Give libtorrent a DHT node and a peer to talk to, the way it would learn them from the swarm
    engine.session.add_dht_node((LOOPBACK, sentinels["dht_node"].port))
    download.handle.connect_peer((LOOPBACK, sentinels["peer"].port))
    return sentinels, engine, download


# Names of the leak targets (everything except the dead proxy) that were contacted
def contacted_targets(sentinels: dict) -> list[str]:
    return [sentinel.name for role, sentinel in sentinels.items() if role != "dead_proxy" and sentinel.contacts]


# Without a proxy every sentinel is reached: the harness can see traffic
def test_positive_control_reaches_all_sentinels(tmp_path):
    with ExitStack() as stack:
        sentinels, _engine, _download = start_scenario(stack, tmp_path, None)
        deadline = time.monotonic() + POSITIVE_CONTROL_SECONDS
        targets = [sentinel for role, sentinel in sentinels.items() if role != "dead_proxy"]
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
        assert sentinels["dead_proxy"].contacts >= 1


# HTTP strict mode: no direct contact, no UDP tracker left, no DHT
def test_http_dead_proxy_leaks_nothing(tmp_path):
    with ExitStack() as stack:
        sentinels, engine, download = start_scenario(stack, tmp_path, ProxyKind.HTTP)
        time.sleep(LEAK_WINDOW_SECONDS)
        assert contacted_targets(sentinels) == []
        assert sentinels["dead_proxy"].contacts >= 1
        assert not [entry["url"] for entry in download.handle.trackers() if entry["url"].startswith("udp://")]
        assert engine.session.get_settings()["enable_dht"] is False


# With a proxy, a direct incoming BitTorrent handshake gets no answer (or there is no listener at all)
def test_incoming_handshake_refused_with_proxy(tmp_path):
    with ExitStack() as stack:
        _sentinels, engine, download = start_scenario(stack, tmp_path, ProxyKind.SOCKS5)
        # libtorrent opens no listening socket in proxy mode: nothing to connect to directly
        if engine.listen_port == 0:
            return
        handshake = b"\x13BitTorrent protocol" + bytes(8) + bytes.fromhex(download.info_hash[:40]) + os.urandom(20)
        reply = b""
        with socket.create_connection((LOOPBACK, engine.listen_port), timeout=HANDSHAKE_WAIT_SECONDS) as connection:
            connection.sendall(handshake)
            try:
                reply = connection.recv(68)
            except (socket.timeout, ConnectionError):
                reply = b""
        assert len(reply) < 68, "a direct incoming peer completed a handshake despite the proxy"
