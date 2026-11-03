# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the download loop shared by the CLI and the GUI."""

import threading

import pytest

from meerko_bittorent.driver import Outcome, drive_download
from meerko_bittorent.errors import TorrentError
from tests.fakes import SEEDING, FakeDownload

MAGNET = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"


# Run the driver with a fresh stop event unless one is given; returns (outcome, reported statuses)
def drive(download, source="file.torrent", stop_event=None):
    statuses = []
    stop_event = stop_event if stop_event is not None else threading.Event()
    outcome = drive_download(download, source, stop_event, statuses.append, poll_interval=0.01)
    return outcome, statuses


# A finished download reports its status and ends FINISHED
def test_finished_download():
    outcome, statuses = drive(FakeDownload("finish"))
    assert outcome is Outcome.FINISHED
    assert statuses == [SEEDING]


# A stop during the magnet metadata wait ends STOPPED without any status
def test_stop_during_metadata_wait():
    stop_event = threading.Event()
    timer = threading.Timer(0.05, stop_event.set)
    timer.start()
    try:
        outcome, statuses = drive(FakeDownload("block_metadata"), source=MAGNET, stop_event=stop_event)
    finally:
        timer.cancel()
    assert outcome is Outcome.STOPPED
    assert statuses == []


# A stop request before polling ends STOPPED
def test_stop_before_polling():
    stop_event = threading.Event()
    stop_event.set()
    outcome, _statuses = drive(FakeDownload("seeding_forever"), stop_event=stop_event)
    assert outcome is Outcome.STOPPED


# Torrent errors are not swallowed; each front-end reports them its own way
def test_torrent_error_propagates():
    with pytest.raises(TorrentError):
        drive(FakeDownload("torrent_error"))
