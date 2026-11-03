# SPDX-License-Identifier: GPL-3.0-or-later
"""Engine tests against real libtorrent, fully offline: torrents are built locally from temp files."""

import os
import threading
import time

import libtorrent as lt
import pytest

from meerko_bittorent.engine import Engine, listen_message
from meerko_bittorent.errors import AlreadyRunningError, TorrentError
from meerko_bittorent.torrent_lock import TorrentLock

LOCAL_LISTEN = "127.0.0.1:0"
MAGNET_HASH = "0123456789abcdef0123456789abcdef01234567"
SEEDING_TIMEOUT_SECONDS = 15


# A local engine that never touches port 6881 or the user's real lock folder
@pytest.fixture
def make_engine(tmp_path):
    engines = []

    # Factory so a test can create two engines sharing one lock folder
    def factory():
        engine = Engine(None, listen_interfaces=LOCAL_LISTEN, lock_directory=tmp_path / "locks")
        engines.append(engine)
        return engine

    yield factory
    # Close every engine the test created
    for engine in engines:
        engine.close()


# Write a 64 KiB random payload and a .torrent describing it; returns (torrent path, data folder)
@pytest.fixture
def local_torrent(tmp_path):
    data_directory = tmp_path / "data"
    data_directory.mkdir()
    payload = data_directory / "payload.bin"
    payload.write_bytes(os.urandom(64 * 1024))

    file_storage = lt.file_storage()
    lt.add_files(file_storage, str(payload))
    creator = lt.create_torrent(file_storage)
    lt.set_piece_hashes(creator, str(data_directory))
    torrent_path = tmp_path / "payload.torrent"
    torrent_path.write_bytes(lt.bencode(creator.generate()))
    return torrent_path, data_directory


# Poll until the download is seeding or the timeout expires
def wait_until_seeding(download):
    deadline = time.monotonic() + SEEDING_TIMEOUT_SECONDS
    # libtorrent checks the existing data first, then switches to seeding
    while time.monotonic() < deadline:
        status = download.poll()
        if status.is_seeding:
            return status
        time.sleep(0.1)
    raise AssertionError("download never reached seeding")


# With the complete data already on disk, the torrent checks and starts seeding
def test_complete_data_reaches_seeding(make_engine, local_torrent):
    torrent_path, data_directory = local_torrent
    download = make_engine().start(str(torrent_path), data_directory)
    status = wait_until_seeding(download)
    assert status.progress == 1.0
    assert status.name == "payload.bin"
    assert status.error is None
    download.close()


# The engine binds a real port (OS-chosen here) and reports it
def test_listen_port_is_reported(make_engine):
    assert make_engine().listen_port > 0


# Closing a download releases its lock for other processes
def test_close_releases_lock(make_engine, local_torrent, tmp_path):
    torrent_path, data_directory = local_torrent
    download = make_engine().start(str(torrent_path), data_directory)
    download.close()
    download.close()
    with TorrentLock(download.info_hash, tmp_path / "locks"):
        pass


# The same torrent in a second engine is refused while the first holds it
def test_same_torrent_twice_raises_already_running(make_engine, local_torrent):
    torrent_path, data_directory = local_torrent
    first = make_engine().start(str(torrent_path), data_directory)
    with pytest.raises(AlreadyRunningError):
        make_engine().start(str(torrent_path), data_directory)
    first.close()


# A .torrent path that does not exist is a torrent error, not a crash
def test_missing_torrent_file_raises_torrent_error(make_engine, tmp_path):
    with pytest.raises(TorrentError):
        make_engine().start(str(tmp_path / "absent.torrent"), tmp_path)


# A file that is not bencoded torrent data is a torrent error
def test_garbage_torrent_file_raises_torrent_error(make_engine, tmp_path):
    garbage = tmp_path / "garbage.torrent"
    garbage.write_bytes(b"this is not a torrent")
    with pytest.raises(TorrentError):
        make_engine().start(str(garbage), tmp_path)


# Malformed magnet links are rejected and leave the engine usable (Review Focus 2)
def test_malformed_magnet_raises_torrent_error(make_engine, local_torrent):
    engine = make_engine()
    with pytest.raises(TorrentError):
        engine.start("magnet:?xt=garbage", local_torrent[1])
    torrent_path, data_directory = local_torrent
    engine.start(str(torrent_path), data_directory).close()


# A magnet's info-hash is known before metadata; a stop request ends the metadata wait
def test_magnet_info_hash_extracted(make_engine, tmp_path):
    download = make_engine().start(f"magnet:?xt=urn:btih:{MAGNET_HASH.upper()}", tmp_path)
    assert download.info_hash == MAGNET_HASH
    stop_event = threading.Event()
    stop_event.set()
    assert download.wait_for_metadata(stop_event) is False
    download.close()


# libtorrent sanitizes "../" in torrent file paths, so files cannot land outside the save folder
def test_dotdot_path_stays_inside_save_path(tmp_path):
    info = {
        "name": "outer",
        "piece length": 16384,
        "pieces": b"\0" * 20,
        "files": [{"length": 10, "path": ["..", "evil.bin"]}],
    }
    torrent_info = lt.torrent_info(lt.bencode({"info": info}))
    save_path = tmp_path / "save"
    resolved = (save_path / torrent_info.files().file_path(0)).resolve()
    assert resolved.is_relative_to(save_path.resolve())


# Port 0 means no listening socket (proxy mode), which deserves a clearer log line
def test_listen_message():
    assert listen_message(0) == "Not accepting incoming connections (proxy mode)"
    assert listen_message(6881) == "Session listening on port 6881"


from meerko_bittorent.engine import filter_trackers, finished_from, named_settings_to_libtorrent, ratio_from
from meerko_bittorent.network import NO_HTTP_TRACKERS_NOTE, ProxyProfile, privacy_summary
from meerko_bittorent.proxy import ProxyKind, ProxySettings

DEAD_SOCKS5 = ProxySettings(ProxyKind.SOCKS5, "127.0.0.1", 9)
DEAD_HTTP = ProxySettings(ProxyKind.HTTP, "127.0.0.1", 9)


# Write a .torrent with the given tracker URLs (data absent); returns its path and save folder
def torrent_with_trackers(directory, tracker_urls):
    payload = directory / "payload.bin"
    payload.write_bytes(os.urandom(16 * 1024))
    file_storage = lt.file_storage()
    lt.add_files(file_storage, str(payload))
    creator = lt.create_torrent(file_storage)
    # Each tracker in its own tier
    for tier, url in enumerate(tracker_urls):
        creator.add_tracker(url, tier)
    lt.set_piece_hashes(creator, str(directory))
    payload.unlink()
    torrent_path = directory / "trackers.torrent"
    torrent_path.write_bytes(lt.bencode(creator.generate()))
    return torrent_path


# Engine with a given proxy, local-only listening and a private lock folder
def engine_with(proxy, tmp_path):
    return Engine(proxy, listen_interfaces="127.0.0.1:0", lock_directory=tmp_path / "locks")


# Each profile's switches really reach the libtorrent session
@pytest.mark.parametrize(
    ("proxy", "dht", "lsd", "anonymous"),
    [(None, True, True, False), (DEAD_SOCKS5, True, False, True), (DEAD_HTTP, False, False, True)],
)
def test_session_builds_for_each_profile(tmp_path, proxy, dht, lsd, anonymous):
    engine = engine_with(proxy, tmp_path)
    try:
        settings = engine.session.get_settings()
        assert (settings["enable_dht"], settings["enable_lsd"], settings["anonymous_mode"]) == (dht, lsd, anonymous)
        assert engine.privacy_summary == privacy_summary(proxy)
    finally:
        engine.close()


# Setting names from network.py become libtorrent's numeric values
def test_named_settings_conversion():
    converted = named_settings_to_libtorrent({
        "out_enc_policy": "pe_enabled",
        "allowed_enc_level": "pe_both",
        "choking_algorithm": "rate_based_choker",
        "proxy_type_name": "socks5_pw",
        "enable_dht": True,
    })
    assert converted["out_enc_policy"] == int(lt.enc_policy.pe_enabled)
    assert converted["allowed_enc_level"] == int(lt.enc_level.pe_both)
    assert converted["choking_algorithm"] == int(lt.choking_algorithm_t.rate_based_choker)
    assert converted["proxy_type"] == int(lt.proxy_type_t.socks5_pw)
    assert "proxy_type_name" not in converted
    assert converted["enable_dht"] is True


# Filtering keeps order and follows the profile
def test_filter_trackers():
    urls = ["udp://a:1", "http://b/announce", "UDP://c:2", "https://d/announce"]
    assert filter_trackers(urls, ProxyProfile.HTTP) == ["http://b/announce", "https://d/announce"]
    assert filter_trackers(urls, ProxyProfile.SOCKS5) == urls


# HTTP mode: UDP trackers are gone from a .torrent before it can announce
def test_http_profile_removes_udp_trackers_from_torrent_file(tmp_path):
    torrent_path = torrent_with_trackers(tmp_path, ["http://127.0.0.1:1/announce", "udp://127.0.0.1:2/announce"])
    engine = engine_with(DEAD_HTTP, tmp_path)
    try:
        download = engine.start(str(torrent_path), tmp_path)
        assert [entry["url"] for entry in download.handle.trackers()] == ["http://127.0.0.1:1/announce"]
        assert download.notes == []
        download.close()
    finally:
        engine.close()


# HTTP mode with only UDP trackers: none left, and the user is told (Review Focus 2)
def test_http_profile_all_udp_trackers_leaves_note(tmp_path):
    torrent_path = torrent_with_trackers(tmp_path, ["udp://127.0.0.1:2/announce"])
    engine = engine_with(DEAD_HTTP, tmp_path)
    try:
        download = engine.start(str(torrent_path), tmp_path)
        assert list(download.handle.trackers()) == []
        assert download.notes == [NO_HTTP_TRACKERS_NOTE]
        download.close()
    finally:
        engine.close()


# HTTP mode: magnet trackers are filtered before the torrent is added
def test_http_profile_filters_magnet_trackers(tmp_path):
    magnet = (
        "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"
        "&tr=udp%3A%2F%2F127.0.0.1%3A2%2Fannounce&tr=http%3A%2F%2F127.0.0.1%3A1%2Fannounce"
    )
    engine = engine_with(DEAD_HTTP, tmp_path)
    try:
        download = engine.start(magnet, tmp_path)
        assert [entry["url"] for entry in download.handle.trackers()] == ["http://127.0.0.1:1/announce"]
        download.close()
    finally:
        engine.close()


# Direct mode keeps every tracker
def test_direct_profile_keeps_udp_trackers(tmp_path):
    torrent_path = torrent_with_trackers(tmp_path, ["http://127.0.0.1:1/announce", "udp://127.0.0.1:2/announce"])
    engine = engine_with(None, tmp_path)
    try:
        download = engine.start(str(torrent_path), tmp_path)
        assert len(list(download.handle.trackers())) == 2
        download.close()
    finally:
        engine.close()


# Protocol overhead does not count towards the 1.0 ratio (Review Focus 4)
def test_finished_uses_payload_counters():
    assert finished_from(True, 10, 100) is False
    assert finished_from(True, 100, 100) is True
    assert finished_from(False, 500, 100) is False
    assert ratio_from(50, 100) == 0.5
    assert ratio_from(50, 0) == 0.0
