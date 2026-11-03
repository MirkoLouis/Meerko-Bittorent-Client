# SPDX-License-Identifier: GPL-3.0-or-later
"""The shared engine: one libtorrent session per process and one Download per torrent.

This is the only module that imports libtorrent. Use only APIs present in libtorrent 2.0.5 through 2.0.12.
"""

import logging
import threading
from pathlib import Path

import libtorrent as lt

from meerko_bittorent.errors import TorrentError
from meerko_bittorent.network import (
    ProxyProfile,
    keeps_tracker,
    keeps_web_seeds,
    no_trackers_note,
    network_settings,
    privacy_summary,
    proxy_profile,
)
from meerko_bittorent.proxy import ProxySettings
from meerko_bittorent.sources import MAGNET_PREFIX
from meerko_bittorent.status import DownloadStatus
from meerko_bittorent.torrent_lock import TorrentLock

logger = logging.getLogger(__name__)

DEFAULT_LISTEN_INTERFACES = "0.0.0.0:6881"
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


# libtorrent enum types for the settings that network.py gives by name
NAMED_SETTING_ENUMS = {
    "out_enc_policy": lt.enc_policy,
    "in_enc_policy": lt.enc_policy,
    "allowed_enc_level": lt.enc_level,
    "choking_algorithm": lt.choking_algorithm_t,
}


# Convert network.py's by-name settings into the numeric values libtorrent expects
def named_settings_to_libtorrent(settings: dict[str, object]) -> dict[str, object]:
    converted = dict(settings)
    # Encryption policy/level and the choker are enums
    for key, enum_type in NAMED_SETTING_ENUMS.items():
        if key in converted:
            converted[key] = int(getattr(enum_type, converted[key]))
    # The proxy type is given as a proxy_type_t member name
    if "proxy_type_name" in converted:
        converted["proxy_type"] = int(getattr(lt.proxy_type_t, converted.pop("proxy_type_name")))
    return converted


# Tracker URLs allowed under this profile, in their original order
def filter_trackers(urls: list[str], profile: ProxyProfile) -> list[str]:
    return [url for url in urls if keeps_tracker(url, profile)]


# Share ratio from payload bytes only (protocol overhead does not count)
def ratio_from(payload_uploaded: int, wanted: int) -> float:
    return payload_uploaded / wanted if wanted > 0 else 0.0


# Done once seeding has uploaded as much payload as was wanted (ratio 1.0)
def finished_from(is_seeding: bool, payload_uploaded: int, wanted: int) -> bool:
    return is_seeding and payload_uploaded >= wanted


# Log line for the bound port; 0 means no listening socket, as with a forced proxy
def listen_message(port: int) -> str:
    if port == 0:
        return "Not accepting incoming connections (proxy mode)"
    return f"Session listening on port {port}"


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
    # Wrap a handle; notes are user-facing remarks such as "no HTTP trackers"
    def __init__(self, session, handle, lock: TorrentLock, info_hash: str, notes: list[str] | None = None) -> None:
        self.session = session
        self.handle = handle
        self.lock = lock
        self.info_hash = info_hash
        self.notes = notes if notes is not None else []
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

        ratio = ratio_from(status.total_payload_upload, status.total_wanted)
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

    # Done once seeding has uploaded as much payload as was wanted (ratio 1.0)
    @property
    def finished(self) -> bool:
        status = self.handle.status()
        return finished_from(status.is_seeding, status.total_payload_upload, status.total_wanted)

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
        # Privacy and performance policy for this proxy (or none), see network.py
        settings.update(named_settings_to_libtorrent(network_settings(proxy)))

        self.session = lt.session(settings)
        self.lock_directory = lock_directory
        self.profile = proxy_profile(proxy)
        self.privacy_summary = privacy_summary(proxy)
        logger.info(listen_message(self.listen_port))

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
            handle, kept_trackers = self.add_with_profile_policy(parameters)
        except RuntimeError as error:
            lock.release()
            raise TorrentError(f"libtorrent refused the torrent: {error}") from None

        notes = []
        note = no_trackers_note(self.profile)
        # In proxy modes a torrent without trackers may find no peers; say so
        if note is not None and not kept_trackers:
            notes.append(note)
        logger.info("Added torrent %s", info_hash)
        return Download(self.session, handle, lock, info_hash, notes)

    # Add the torrent so it never contacts a tracker or web seed the profile forbids; returns (handle, kept trackers)
    def add_with_profile_policy(self, parameters) -> tuple[object, list[str]]:
        keep_web_seeds = keeps_web_seeds(self.profile)

        # Magnets: filter trackers and web seeds (ws=) before adding
        if parameters.ti is None:
            parameters.trackers = filter_trackers(list(parameters.trackers), self.profile)
            if not keep_web_seeds:
                parameters.url_seeds = []
            return self.session.add_torrent(parameters), list(parameters.trackers)

        all_trackers = [entry.url for entry in parameters.ti.trackers()]
        kept_trackers = filter_trackers(all_trackers, self.profile)
        removed_web_seeds = [] if keep_web_seeds else [seed["url"] for seed in parameters.ti.web_seeds()]
        # Nothing to remove: add normally
        if kept_trackers == all_trackers and not removed_web_seeds:
            return self.session.add_torrent(parameters), kept_trackers

        # .torrent trackers and web seeds live in the metadata: add paused, remove them, then start
        parameters.flags |= lt.torrent_flags.paused
        parameters.flags &= ~lt.torrent_flags.auto_managed
        handle = self.session.add_torrent(parameters)
        if kept_trackers != all_trackers:
            handle.replace_trackers([lt.announce_entry(url) for url in kept_trackers])
        # A web seed is either a url-seed or an http-seed; removing an absent one is a no-op
        for url in removed_web_seeds:
            handle.remove_url_seed(url)
            handle.remove_http_seed(url)
        handle.resume()
        return handle, kept_trackers

    # Stop all network activity of this session
    def close(self) -> None:
        self.session.pause()
