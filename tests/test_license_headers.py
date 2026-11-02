# SPDX-License-Identifier: GPL-3.0-or-later
"""Every Python source file must carry the project's SPDX license header."""

from pathlib import Path

SPDX_HEADER = "# SPDX-License-Identifier: GPL-3.0-or-later"
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIRECTORIES = ("meerko_bittorent", "tests", "packaging")


# Collect every .py file under the source directories that exist
def find_python_files():
    python_files = []
    # Walk each source directory; packaging/ may not exist yet
    for directory_name in SOURCE_DIRECTORIES:
        directory = REPOSITORY_ROOT / directory_name
        if not directory.is_dir():
            continue
        python_files.extend(sorted(directory.rglob("*.py")))
    return python_files


# Read only the first line of a file, tolerating empty files
def read_first_line(path):
    with path.open(encoding="utf-8") as source_file:
        return source_file.readline().rstrip("\r\n")


def test_every_python_file_has_spdx_header():
    missing_header = [
        str(path.relative_to(REPOSITORY_ROOT))
        for path in find_python_files()
        if read_first_line(path) != SPDX_HEADER
    ]
    assert missing_header == [], f"Missing SPDX header: {missing_header}"
