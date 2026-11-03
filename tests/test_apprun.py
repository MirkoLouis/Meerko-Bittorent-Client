# SPDX-License-Identifier: GPL-3.0-or-later
"""AppRun routes `cli` to the command-line binary and everything else to the GUI."""

import os
import subprocess
from pathlib import Path

import pytest

APPRUN_PATH = Path(__file__).resolve().parent.parent / "packaging" / "appimage" / "AppRun"
BINARY_NAMES = ("meerko-bittorent", "meerko-bittorent-cli")

pytestmark = pytest.mark.skipif(os.name == "nt", reason="AppRun is a POSIX shell script")


# Fake AppDir whose two binaries just print their own name and arguments
@pytest.fixture
def fake_app_directory(tmp_path):
    binary_directory = tmp_path / "usr" / "lib" / "meerko-bittorent"
    binary_directory.mkdir(parents=True)
    # Each fake binary echoes what it was called with
    for binary_name in BINARY_NAMES:
        binary = binary_directory / binary_name
        binary.write_text(f'#!/bin/sh\necho {binary_name} "$@"\n', encoding="utf-8")
        binary.chmod(0o755)
    return tmp_path


# Run AppRun with APPDIR pointing at the fake tree and return its output
def run_apprun(app_directory: Path, *arguments: str) -> str:
    environment = dict(os.environ, APPDIR=str(app_directory))
    result = subprocess.run(
        ["sh", str(APPRUN_PATH), *arguments], env=environment, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


# `cli` is consumed and the remaining arguments go to the CLI binary
def test_apprun_routes_cli(fake_app_directory):
    assert run_apprun(fake_app_directory, "cli", "--version") == "meerko-bittorent-cli --version"


# Anything else launches the GUI with the arguments untouched
def test_apprun_defaults_to_gui(fake_app_directory):
    assert run_apprun(fake_app_directory, "x") == "meerko-bittorent x"
    assert run_apprun(fake_app_directory) == "meerko-bittorent"
