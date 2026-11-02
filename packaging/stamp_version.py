# SPDX-License-Identifier: GPL-3.0-or-later
"""Write a validated release version into meerko_bittorent/__init__.py.

Usage: python packaging/stamp_version.py <version>   (a leading "v", as in git tags, is stripped)
"""

import re
import sys
from pathlib import Path

# PEP 440 subset: X.Y.Z with optional aN/bN/rcN and optional .devN; nothing else is accepted
VERSION_PATTERN = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+((a|b|rc)[0-9]+)?(\.dev[0-9]+)?")
VERSION_LINE_PATTERN = re.compile(r'^__version__ = ".*"$', re.MULTILINE)
DEFAULT_INIT_PATH = Path(__file__).resolve().parent.parent / "meerko_bittorent" / "__init__.py"


# Replace the single __version__ line in init_path; raise ValueError on any doubt
def stamp_version(init_path: Path, version: str) -> None:
    # Reject the version before touching the file (fullmatch also rejects trailing newlines)
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"invalid version {version!r}; expected e.g. 1.2.3, 1.2.3rc1 or 1.2.3.dev0")

    source = init_path.read_text(encoding="utf-8")
    match_count = len(VERSION_LINE_PATTERN.findall(source))

    # Exactly one version line, otherwise we cannot know which one is authoritative
    if match_count != 1:
        raise ValueError(f"expected exactly one __version__ line in {init_path}, found {match_count}")

    stamped = VERSION_LINE_PATTERN.sub(f'__version__ = "{version}"', source)
    init_path.write_text(stamped, encoding="utf-8")


# Command-line wrapper: returns 0 on success, 2 on usage or validation errors
def main(argv: list[str], init_path: Path | None = None) -> int:
    # Exactly one positional argument: the version or tag
    if len(argv) != 1:
        print("usage: stamp_version.py <version>", file=sys.stderr)
        return 2

    # Git tags look like v1.2.3; strip a single leading "v"
    version = argv[0].removeprefix("v")
    target_path = init_path if init_path is not None else DEFAULT_INIT_PATH

    try:
        stamp_version(target_path, version)
    except ValueError as error:
        print(f"stamp_version: {error}", file=sys.stderr)
        return 2

    print(f"stamped {target_path} with version {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
