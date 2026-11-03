# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the info-hash lock, using real second processes as the competing holder."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from meerko_bittorent.errors import AlreadyRunningError
from meerko_bittorent.torrent_lock import TorrentLock

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
INFO_HASH = "0123456789abcdef0123456789abcdef01234567"

# The holder takes the lock, reports it, then keeps it until its stdin is closed
HOLDER_SCRIPT = """
import sys
from pathlib import Path
from meerko_bittorent.torrent_lock import TorrentLock
lock = TorrentLock(sys.argv[1], Path(sys.argv[2]))
lock.acquire()
print("locked", flush=True)
sys.stdin.read()
"""


# Start a holder process and wait until it reports that it owns the lock
def start_holder(lock_directory: Path) -> subprocess.Popen:
    environment = dict(os.environ, PYTHONPATH=str(REPOSITORY_ROOT))
    holder = subprocess.Popen(
        [sys.executable, "-c", HOLDER_SCRIPT, INFO_HASH, str(lock_directory)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        env=environment,
    )
    assert holder.stdout.readline().strip() == "locked"
    return holder


# While another process holds the lock, acquiring fails immediately
def test_second_process_is_refused(tmp_path):
    holder = start_holder(tmp_path)
    try:
        with pytest.raises(AlreadyRunningError):
            TorrentLock(INFO_HASH, tmp_path).acquire()
    finally:
        holder.stdin.close()
        holder.wait(timeout=10)


# A holder that exits normally releases the lock
def test_released_after_holder_exits(tmp_path):
    holder = start_holder(tmp_path)
    holder.stdin.close()
    holder.wait(timeout=10)
    with TorrentLock(INFO_HASH, tmp_path):
        pass


# A holder that is killed releases the lock too (the OS drops it with the process)
def test_released_after_holder_is_killed(tmp_path):
    holder = start_holder(tmp_path)
    holder.kill()
    holder.wait(timeout=10)
    holder.stdin.close()
    with TorrentLock(INFO_HASH, tmp_path):
        pass


# Releasing makes the lock available again within the same process; release is idempotent
def test_same_process_reacquire_after_release(tmp_path):
    first = TorrentLock(INFO_HASH, tmp_path)
    first.acquire()
    first.release()
    first.release()
    with TorrentLock(INFO_HASH, tmp_path):
        pass


# The hash becomes a file name, so anything but lower-case hex of the right length is refused
@pytest.mark.parametrize("bad_hash", ["../etc", "ABC", "", "0" * 39, "g" * 40, INFO_HASH.upper()])
def test_rejects_non_hex_hash(tmp_path, bad_hash):
    with pytest.raises(ValueError):
        TorrentLock(bad_hash, tmp_path)


# v2 (SHA-256) info-hashes are 64 hex characters
def test_accepts_v2_hash(tmp_path):
    with TorrentLock("a" * 64, tmp_path):
        pass
