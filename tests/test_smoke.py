# SPDX-License-Identifier: GPL-3.0-or-later
"""Smoke tests: the package, its entry point and its native dependencies load."""


# The development version is the single source the release stamping rewrites
def test_version_is_dev_string():
    import meerko_bittorent

    assert meerko_bittorent.__version__ == "1.0.0.dev0"


# The gui-script entry point in pyproject.toml must resolve to a callable
def test_main_entry_point_is_callable():
    from meerko_bittorent.__main__ import main

    assert callable(main)


# libtorrent bindings are present and from the supported 2.0.x series
def test_libtorrent_importable():
    import libtorrent

    assert libtorrent.__version__.startswith("2.0")


# tkinter is importable; never instantiate Tk (no display in CI or the Nix sandbox)
def test_tkinter_importable():
    import tkinter

    assert tkinter.TkVersion >= 8.6
