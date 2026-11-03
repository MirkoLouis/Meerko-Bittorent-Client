# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the shared error types and the one-line status shown by both front-ends."""

from meerko_bittorent.errors import AlreadyRunningError, InputError, MeerkoError, TorrentError
from meerko_bittorent.status import DownloadStatus, format_rate, format_status


# Build a status with sensible defaults so each test states only what it cares about
def make_status(**overrides):
    fields = {
        "name": "example",
        "state": "downloading",
        "progress": 0.421,
        "download_rate": 1_200_000,
        "upload_rate": 210_000,
        "peers": 18,
        "ratio": 0.0,
        "is_seeding": False,
        "error": None,
    }
    fields.update(overrides)
    return DownloadStatus(**fields)


# Rates use decimal units (1 kB = 1000 B), one decimal place
def test_format_rate_units():
    assert format_rate(0) == "0 B/s"
    assert format_rate(1500) == "1.5 kB/s"
    assert format_rate(2_500_000) == "2.5 MB/s"


# The downloading line shows progress, peers, both rates and the state
def test_format_status_downloading():
    assert format_status(make_status()) == "42.10% | 18 peers | ↓ 1.2 MB/s ↑ 210.0 kB/s | downloading"


# While seeding, the share ratio is appended
def test_format_status_seeding_shows_ratio():
    seeding = make_status(state="seeding", progress=1.0, is_seeding=True, ratio=0.5)
    assert format_status(seeding).endswith("| ratio 0.50")


# An error replaces the whole line
def test_format_status_error_wins():
    assert format_status(make_status(error="disk full")) == "Error: disk full"


# Front-ends catch MeerkoError and branch on the subclass
def test_error_hierarchy():
    for error_type in (InputError, TorrentError, AlreadyRunningError):
        assert issubclass(error_type, MeerkoError)
