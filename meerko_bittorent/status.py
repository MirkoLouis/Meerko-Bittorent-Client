# SPDX-License-Identifier: GPL-3.0-or-later
"""A libtorrent-free snapshot of a download, and the one-line text both front-ends display."""

from dataclasses import dataclass

RATE_UNITS = ("B/s", "kB/s", "MB/s", "GB/s")


# Plain snapshot of one download; front-ends never see libtorrent objects
@dataclass(frozen=True)
class DownloadStatus:
    name: str
    state: str
    progress: float
    download_rate: int
    upload_rate: int
    peers: int
    ratio: float
    is_seeding: bool
    error: str | None = None


# Human-readable transfer rate in decimal units (1 kB = 1000 B)
def format_rate(bytes_per_second: int) -> str:
    # Whole bytes need no decimal place
    if bytes_per_second < 1000:
        return f"{bytes_per_second} B/s"

    value = float(bytes_per_second)
    unit_index = 0
    # Scale down until the value fits the unit, stopping at the largest unit
    while value >= 1000 and unit_index < len(RATE_UNITS) - 1:
        value /= 1000
        unit_index += 1
    return f"{value:.1f} {RATE_UNITS[unit_index]}"


# The single status line shown by the CLI progress output and the GUI status label
def format_status(status: DownloadStatus) -> str:
    # An error replaces everything else on the line
    if status.error:
        return f"Error: {status.error}"

    line = (
        f"{status.progress * 100:.2f}% | "
        f"{status.peers} peers | "
        f"↓ {format_rate(status.download_rate)} ↑ {format_rate(status.upload_rate)} | "
        f"{status.state}"
    )
    # Seeding shows how far we are towards the 1.0 ratio stop
    if status.is_seeding:
        line += f" | ratio {status.ratio:.2f}"
    return line
