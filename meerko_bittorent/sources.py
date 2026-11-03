# SPDX-License-Identifier: GPL-3.0-or-later
"""Validation of user-supplied torrent sources and save folders, shared by the CLI and the GUI."""

import tempfile
from pathlib import Path

from meerko_bittorent.errors import InputError

MAGNET_PREFIX = "magnet:"


# Absolute save folder; it must be a folder or not exist yet (it is then created)
def prepare_save_path(raw_path: str) -> Path:
    save_path = Path(raw_path).expanduser().resolve()
    # An existing file where a folder should be is a usage error
    if save_path.exists() and not save_path.is_dir():
        raise InputError(f"save path {save_path} exists and is not a folder")
    try:
        save_path.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise InputError(f"cannot create save folder {save_path}: {error.strerror}") from None

    # Prove the folder is writable now, instead of failing later as a disk error (after a metadata wait)
    try:
        with tempfile.TemporaryFile(dir=save_path):
            pass
    except OSError as error:
        raise InputError(f"cannot write to save folder {save_path}: {error.strerror}") from None
    return save_path


# Magnet links pass through; .torrent paths become absolute and must be existing files
def prepare_source(raw_source: str) -> str:
    if raw_source.startswith(MAGNET_PREFIX):
        return raw_source
    torrent_path = Path(raw_source).expanduser().resolve()
    # Catch typos before libtorrent does, with a clearer message
    if not torrent_path.is_file():
        raise InputError(f"torrent file not found: {torrent_path}")
    return str(torrent_path)
