# SPDX-License-Identifier: GPL-3.0-or-later
"""Error types shared by the engine and both front-ends.

str(error) is always a message a user can read; the CLI maps each subclass to an exit code.
"""


# Base class: anything Meerko reports to the user rather than crashing on
class MeerkoError(Exception):
    pass


# Bad flags, invalid proxy settings, unreadable config, missing password without a terminal
class InputError(MeerkoError):
    pass


# Unreadable .torrent / magnet, or a torrent or disk error reported by libtorrent
class TorrentError(MeerkoError):
    pass


# Another Meerko process already holds this torrent's lock
class AlreadyRunningError(MeerkoError):
    pass
