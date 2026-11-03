# SPDX-License-Identifier: GPL-3.0-or-later
"""Scripted stand-ins for engine.Engine and engine.Download, shared by the CLI and GUI tests."""

import threading

from meerko_bittorent.errors import AlreadyRunningError, TorrentError
from meerko_bittorent.status import DownloadStatus

SEEDING = DownloadStatus("x", "seeding", 1.0, 0, 0, 3, 1.0, True)


# Scripted stand-in for engine.Download
class FakeDownload:
    def __init__(self, behaviour: str) -> None:
        self.behaviour = behaviour
        self.close_calls = 0

    # "block_metadata" waits until the CLI's stop event is set, like a magnet with no peers
    def wait_for_metadata(self, stop_event: threading.Event, poll_interval: float = 0.1) -> bool:
        if self.behaviour == "block_metadata":
            stop_event.wait()
            return False
        return True

    # "torrent_error" fails on the first poll; everything else is already seeding
    def poll(self) -> DownloadStatus:
        if self.behaviour == "torrent_error":
            raise TorrentError("disk full")
        return SEEDING

    @property
    def finished(self) -> bool:
        return self.behaviour == "finish"

    def close(self) -> None:
        self.close_calls += 1


# Scripted stand-in for engine.Engine; records the proxy it was built with
class FakeEngine:
    def __init__(self, behaviour: str) -> None:
        self.behaviour = behaviour
        self.proxy = None
        self.download = FakeDownload(behaviour)

    # Matches the engine_factory signature: called with the effective proxy
    def __call__(self, proxy):
        self.proxy = proxy
        return self

    def start(self, source, save_path):
        if self.behaviour == "already_running":
            raise AlreadyRunningError("this torrent is already being downloaded by another Meerko process")
        return self.download

    def close(self) -> None:
        pass
