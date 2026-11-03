# SPDX-License-Identifier: GPL-3.0-or-later
"""A cross-process lock per torrent, so the same torrent never runs in two Meerko processes.

The lock is an OS file lock (flock on POSIX, msvcrt.locking on Windows) on <lock dir>/<info-hash>.lock.
The OS drops it when the process exits or dies, so a crash never leaves a stale lock behind.
"""

import os
import re
from pathlib import Path

from meerko_bittorent.config import APPLICATION_DIRECTORY, user_base_directory
from meerko_bittorent.errors import AlreadyRunningError

# v1 info-hashes are SHA-1 (40 hex), v2 are SHA-256 (64 hex); the hash becomes a file name
INFO_HASH_PATTERN = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
ALREADY_RUNNING_MESSAGE = "this torrent is already being downloaded by another Meerko process"

# Pick the platform's non-blocking lock primitives once, at import time
if os.name == "nt":
    import msvcrt

    # Lock the first byte without waiting; raises OSError if another process holds it
    def lock_file_descriptor(file_descriptor: int) -> None:
        msvcrt.locking(file_descriptor, msvcrt.LK_NBLCK, 1)

    # Unlock the first byte
    def unlock_file_descriptor(file_descriptor: int) -> None:
        os.lseek(file_descriptor, 0, os.SEEK_SET)
        msvcrt.locking(file_descriptor, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    # Exclusive lock without waiting; raises BlockingIOError if another process holds it
    def lock_file_descriptor(file_descriptor: int) -> None:
        fcntl.flock(file_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)

    # Drop the lock
    def unlock_file_descriptor(file_descriptor: int) -> None:
        fcntl.flock(file_descriptor, fcntl.LOCK_UN)


# Per-user cache folder for lock files
def default_lock_directory() -> Path:
    return user_base_directory("XDG_CACHE_HOME", ".cache", "LOCALAPPDATA") / APPLICATION_DIRECTORY / "locks"


# Context manager holding the lock for one info-hash
class TorrentLock:
    # Validate the hash before it is used as a file name
    def __init__(self, info_hash_hex: str, lock_directory: Path | None = None) -> None:
        if not INFO_HASH_PATTERN.fullmatch(info_hash_hex):
            raise ValueError(f"not a lower-case hex info-hash: {info_hash_hex!r}")
        directory = lock_directory if lock_directory is not None else default_lock_directory()
        self.lock_path = directory / f"{info_hash_hex}.lock"
        self.file_descriptor: int | None = None

    # Take the lock or raise AlreadyRunningError; never waits
    def acquire(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            lock_file_descriptor(file_descriptor)
        except OSError:
            os.close(file_descriptor)
            raise AlreadyRunningError(ALREADY_RUNNING_MESSAGE) from None
        self.file_descriptor = file_descriptor

    # Release the lock; safe to call more than once. The file stays (deleting it would race other processes)
    def release(self) -> None:
        if self.file_descriptor is None:
            return
        try:
            unlock_file_descriptor(self.file_descriptor)
        finally:
            os.close(self.file_descriptor)
            self.file_descriptor = None

    def __enter__(self) -> "TorrentLock":
        self.acquire()
        return self

    def __exit__(self, *exception_info: object) -> None:
        self.release()
