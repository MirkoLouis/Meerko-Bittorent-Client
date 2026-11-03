# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the GUI's Tk-free logic: form conversion and the download worker. No window is created."""

import queue
import threading
from pathlib import Path

import pytest

from meerko_bittorent import ui
from meerko_bittorent.errors import InputError
from meerko_bittorent.proxy import ProxyKind, ProxySettings
from tests.fakes import FakeEngine

MAGNET = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"


# Run the worker to completion and return every message it sent
def run_worker(engine, source="file.torrent", stop_event=None):
    messages = queue.Queue()
    stop_event = stop_event if stop_event is not None else threading.Event()
    ui.run_download_worker(engine, None, source, Path("/tmp/save"), stop_event, messages, poll_interval=0.01)
    collected = []
    # Drain everything the worker queued
    while not messages.empty():
        collected.append(messages.get_nowait())
    return collected


# An unticked proxy box means no proxy, whatever the fields say
def test_form_disabled_proxy_returns_none():
    assert ui.form_to_proxy(False, "socks5", "", "abc", "", "") is None


# A complete form becomes validated settings; empty optional fields become None
def test_form_valid_socks5():
    assert ui.form_to_proxy(True, "socks5", " proxy.example ", "1080", "", "") == ProxySettings(
        ProxyKind.SOCKS5, "proxy.example", 1080
    )
    with_login = ui.form_to_proxy(True, "http", "h", "8080", "me", "pw")
    assert with_login == ProxySettings(ProxyKind.HTTP, "h", 8080, "me", "pw")


# Non-numeric and out-of-range ports are reported, not crashed on
@pytest.mark.parametrize("port_text", ["abc", "70000", "", "-1"])
def test_form_bad_port_raises_input_error(port_text):
    with pytest.raises(InputError):
        ui.form_to_proxy(True, "socks5", "h", port_text, "", "")


# The GUI cannot prompt later, so a username needs its password in the form
def test_form_username_without_password_raises():
    with pytest.raises(InputError):
        ui.form_to_proxy(True, "socks5", "h", "1080", "me", "")


# A finished download ends with FinishedMessage after at least one status
def test_worker_reports_finished():
    messages = run_worker(FakeEngine("finish"))
    assert isinstance(messages[0], ui.StatusMessage)
    assert isinstance(messages[-1], ui.FinishedMessage)


# A lock conflict becomes the user-facing "already being downloaded" message
def test_worker_reports_already_running_message():
    messages = run_worker(FakeEngine("already_running"))
    assert isinstance(messages[-1], ui.ErrorMessage)
    assert "Already being downloaded by another Meerko process" in messages[-1].text


# Torrent errors are shown, never reported as finished
def test_worker_reports_torrent_error():
    engine = FakeEngine("torrent_error")
    messages = run_worker(engine)
    assert isinstance(messages[-1], ui.ErrorMessage)
    assert "disk full" in messages[-1].text
    assert engine.download.close_calls == 1


# Closing the window during a magnet metadata wait stops and cleans up (Review Focus 5)
def test_worker_stops_during_metadata_wait():
    engine = FakeEngine("block_metadata")
    stop_event = threading.Event()
    timer = threading.Timer(0.1, stop_event.set)
    timer.start()
    try:
        messages = run_worker(engine, source=MAGNET, stop_event=stop_event)
    finally:
        timer.cancel()
    assert isinstance(messages[-1], ui.StoppedMessage)
    assert engine.download.close_calls == 1


# The GUI module itself never touches libtorrent; only engine.py does
def test_ui_does_not_import_libtorrent():
    assert "lt" not in vars(ui)
    assert "libtorrent" not in vars(ui)
