# SPDX-License-Identifier: GPL-3.0-or-later
"""The download loop shared by the CLI and the GUI: metadata wait, polling, finish or stop.

Front-ends only decide how to show statuses and outcomes; torrent errors propagate to them unchanged.
"""

import threading
from collections.abc import Callable
from enum import Enum

from meerko_bittorent.sources import MAGNET_PREFIX
from meerko_bittorent.status import DownloadStatus


# How a download ended when no error occurred
class Outcome(Enum):
    FINISHED = "finished"
    STOPPED = "stopped"


# Wait for metadata (magnets), then report a status every poll_interval until finished or stopped
def drive_download(
    download,
    source: str,
    stop_event: threading.Event,
    on_status: Callable[[DownloadStatus], None],
    poll_interval: float = 1.0,
) -> Outcome:
    # Magnets need their metadata from peers before anything can be downloaded
    if source.startswith(MAGNET_PREFIX) and not download.wait_for_metadata(stop_event):
        return Outcome.STOPPED

    # Poll until the 1.0 ratio is reached or a stop is requested
    while not stop_event.is_set():
        on_status(download.poll())
        if download.finished:
            return Outcome.FINISHED
        stop_event.wait(poll_interval)
    return Outcome.STOPPED
