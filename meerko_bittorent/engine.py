# SPDX-License-Identifier: GPL-3.0-or-later
"""The shared engine: one libtorrent session per process and one Download per torrent.

This is the only module that imports libtorrent. Use only APIs present in libtorrent 2.0.5 through 2.0.12.
"""

import logging
import threading
from pathlib import Path

import libtorrent as lt

from meerko_bittorent.errors import TorrentError
from meerko_bittorent.proxy import ProxySettings
from meerko_bittorent.status import DownloadStatus
from meerko_bittorent.torrent_lock import TorrentLock

logger = logging.getLogger(__name__)

DEFAULT_LISTEN_INTERFACES = "0.0.0.0:6881"
MAGNET_PREFIX = "magnet:"
# torrent_status.state values in libtorrent 2.0 (index 0 and 6 are unused there)
STATE_NAMES = (
    "queued",
    "checking",
    "downloading metadata",
    "downloading",
    "finished",
    "seeding",
    "allocating",
    "checking resume data",
)


# libtorrent's version string, for --version output and diagnostics
def libtorrent_version() -> str:
    return lt.__version__


# Throughput and port-forwarding settings (unchanged from the former client.py; sub-project 3 revisits them)
def performance_settings() -> dict[str, object]:
    return {
        # Enable UPnP and NAT-PMP for port forwarding
        "enable_upnp": True,
        "enable_natpmp": True,
        # 16384 blocks of 16 KiB = 256 MiB cache
        "cache_size": 16384,
        "connections_limit": 1000,
        "active_downloads": 1,
        "active_seeds": -1,
        "choking_algorithm": int(lt.choking_algorithm_t.rate_based_choker),
        "send_buffer_watermark": 500 * 1024,
    }


# libtorrent settings for a proxy; routing flags unchanged from the former client.py
def proxy_session_settings(proxy: ProxySettings) -> dict[str, object]:
    settings = proxy.to_libtorrent()
    type_name = settings.pop("proxy_type_name")
    settings["proxy_type"] = int(getattr(lt.proxy_type_t, type_name))
    # Force all connections through the proxy and avoid identifying information
    settings["force_proxy"] = True
    settings["anonymous_mode"] = True
    return settings


# Hex info-hash of a torrent: v1 (SHA-1) when present, else v2 (SHA-256)
def best_info_hash(info_hashes) -> str:
    if info_hashes.has_v1():
        return str(info_hashes.v1).lower()
    return str(info_hashes.v2).lower()


# Build add_torrent_params from a magnet link or a .torrent file path
def torrent_parameters(source: str, save_path: Path):
    # Magnet links carry the info-hash; metadata is fetched from peers later
    if source.startswith(MAGNET_PREFIX):
        try:
            parameters = lt.parse_magnet_uri(source)
        except RuntimeError as error:
            raise TorrentError(f"invalid magnet link: {error}") from None
        parameters.save_path = str(save_path)
        return parameters, best_info_hash(parameters.info_hashes)

    torrent_path = Path(source)
    # The CLI validates paths too, but the engine must not trust its callers
    if not torrent_path.is_file():
        raise TorrentError(f"torrent file not found: {torrent_path}")

    try:
        torrent_info = lt.torrent_info(str(torrent_path))
    except RuntimeError as error:
        raise TorrentError(f"cannot read torrent file {torrent_path}: {error}") from None

    parameters = lt.add_torrent_params()
    parameters.ti = torrent_info
    parameters.save_path = str(save_path)
    return parameters, best_info_hash(torrent_info.info_hashes())


# One torrent in the session, plus the lock that keeps other processes off it
class Download:
    def __init__(self, session, handle, lock: TorrentLock, info_hash: str) -> None:
        self.session = session
        self.handle = handle
        self.lock = lock
        self.info_hash = info_hash
        self.closed = False

    # Wait until a magnet's metadata arrives; False if stop_event was set first
    def wait_for_metadata(self, stop_event: threading.Event, poll_interval: float = 0.1) -> bool:
        # A stop request always wins, even if metadata is already present
        while not stop_event.is_set():
            if self.handle.status().has_metadata:
                return True
            stop_event.wait(poll_interval)
        return False

    # Snapshot of the download; raises TorrentError if libtorrent reports an error on it
    def poll(self) -> DownloadStatus:
        status = self.handle.status()
        # Disk-full, permission and similar errors stop the torrent and must be shown
        if status.errc.value() != 0:
            raise TorrentError(status.errc.message())

        ratio = status.total_upload / status.total_wanted if status.total_wanted > 0 else 0.0
        state_index = int(status.state)
        state_name = STATE_NAMES[state_index] if state_index < len(STATE_NAMES) else "unknown"
        return DownloadStatus(
            name=status.name,
            state=state_name,
            progress=status.progress,
            download_rate=status.download_rate,
            upload_rate=status.upload_rate,
            peers=status.num_peers,
            ratio=ratio,
            is_seeding=status.is_seeding,
        )

    # Done once seeding has uploaded as much as was downloaded (ratio 1.0, unchanged from before)
    @property
    def finished(self) -> bool:
        status = self.handle.status()
        return status.is_seeding and status.total_upload >= status.total_wanted

    # Remove the torrent and release the lock; safe to call more than once
    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.session.remove_torrent(self.handle)
        finally:
            self.lock.release()


# One libtorrent session; listen_interfaces and lock_directory are overridable for tests
class Engine:
    def __init__(
        self,
        proxy: ProxySettings | None,
        listen_interfaces: str = DEFAULT_LISTEN_INTERFACES,
        lock_directory: Path | None = None,
    ) -> None:
        settings: dict[str, object] = {
            "listen_interfaces": listen_interfaces,
            # If the port is taken (e.g. another Meerko process), let the OS pick a free one
            "listen_system_port_fallback": True,
        }
        settings.update(performance_settings())
        # A proxy, when given, applies to every connection of this session
        if proxy is not None:
            settings.update(proxy_session_settings(proxy))

        self.session = lt.session(settings)
        self.lock_directory = lock_directory
        logger.info("Session listening on port %d", self.listen_port)

    # The port actually bound (may differ from the requested one after fallback)
    @property
    def listen_port(self) -> int:
        return self.session.listen_port()

    # Lock the torrent, then add it; the lock is released again if adding fails
    def start(self, source: str, save_path: Path) -> Download:
        parameters, info_hash = torrent_parameters(source, save_path)
        lock = TorrentLock(info_hash, self.lock_directory)
        lock.acquire()

        try:
            handle = self.session.add_torrent(parameters)
        except RuntimeError as error:
            lock.release()
            raise TorrentError(f"libtorrent refused the torrent: {error}") from None

        logger.info("Added torrent %s", info_hash)
        return Download(self.session, handle, lock, info_hash)

    # Stop all network activity of this session
    def close(self) -> None:
        self.session.pause()
