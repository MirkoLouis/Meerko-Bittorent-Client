# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for packaging/stamp_version.py, which writes the release version into __init__.py."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "packaging" / "stamp_version.py"
ORIGINAL_INIT = (
    '# SPDX-License-Identifier: GPL-3.0-or-later\n'
    '"""Docstring."""\n'
    '\n'
    '__version__ = "1.0.0.dev0"\n'
)


# Load the script by file path; packaging/ must never become an importable package
def load_stamp_module():
    module_spec = importlib.util.spec_from_file_location("stamp_version", SCRIPT_PATH)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


@pytest.fixture
def stamp_module():
    return load_stamp_module()


@pytest.fixture
def init_file(tmp_path):
    path = tmp_path / "__init__.py"
    path.write_text(ORIGINAL_INIT, encoding="utf-8")
    return path


def test_rewrites_version_line(stamp_module, init_file):
    stamp_module.stamp_version(init_file, "1.2.3")
    expected = ORIGINAL_INIT.replace('"1.0.0.dev0"', '"1.2.3"')
    assert init_file.read_text(encoding="utf-8") == expected


@pytest.mark.parametrize(
    "bad_version",
    ["", "1.0", "1.0.0; rm -rf /", "1.0.0\n", "../1.0.0", "v1.0.0", '1.0.0"\nimport os'],
)
def test_rejects_invalid_version(stamp_module, init_file, bad_version):
    with pytest.raises(ValueError):
        stamp_module.stamp_version(init_file, bad_version)
    assert init_file.read_text(encoding="utf-8") == ORIGINAL_INIT


def test_accepts_prerelease_and_dev_versions(stamp_module, init_file):
    stamp_module.stamp_version(init_file, "1.1.0rc2")
    assert '__version__ = "1.1.0rc2"' in init_file.read_text(encoding="utf-8")
    stamp_module.stamp_version(init_file, "1.1.0.dev3")
    assert '__version__ = "1.1.0.dev3"' in init_file.read_text(encoding="utf-8")


def test_fails_when_version_line_missing(stamp_module, tmp_path):
    path = tmp_path / "__init__.py"
    path.write_text('"""No version here."""\n', encoding="utf-8")
    with pytest.raises(ValueError):
        stamp_module.stamp_version(path, "1.2.3")


def test_fails_when_version_line_duplicated(stamp_module, tmp_path):
    path = tmp_path / "__init__.py"
    duplicated = ORIGINAL_INIT + '__version__ = "9.9.9"\n'
    path.write_text(duplicated, encoding="utf-8")
    with pytest.raises(ValueError):
        stamp_module.stamp_version(path, "1.2.3")
    assert path.read_text(encoding="utf-8") == duplicated


def test_cli_strips_leading_v(stamp_module, init_file):
    assert stamp_module.main(["v2.0.0"], init_path=init_file) == 0
    assert '__version__ = "2.0.0"' in init_file.read_text(encoding="utf-8")


def test_cli_returns_2_on_invalid(stamp_module, init_file):
    assert stamp_module.main(["bad"], init_path=init_file) == 2
    assert init_file.read_text(encoding="utf-8") == ORIGINAL_INIT


def test_cli_returns_2_without_exactly_one_argument(stamp_module, init_file):
    assert stamp_module.main([], init_path=init_file) == 2
    assert stamp_module.main(["1.0.0", "2.0.0"], init_path=init_file) == 2
