# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the Linux portal file chooser: request contents, answers, fallback and result delivery.

No real D-Bus is used: the portal and the Tk chooser are injected, and tests drive the scheduler by hand.
"""

import pytest

from meerko_bittorent import file_dialogs
from meerko_bittorent.file_dialogs import (
    DialogKind,
    PortalUnavailable,
    build_open_file_options,
    choose_path,
    request_path,
    response_to_path,
    uri_to_path,
)


# Collects scheduled callbacks so a test can run the polling loop step by step
class ManualScheduler:
    def __init__(self) -> None:
        self.callbacks = []

    # Same shape as tkinter's widget.after(delay_ms, callback)
    def __call__(self, delay_ms, callback):
        self.callbacks.append(callback)

    # Run scheduled callbacks (which may schedule more) until none remain or the limit is hit
    def run_until_idle(self, limit=1000):
        steps = 0
        # Each poll either delivers the result or reschedules itself
        while self.callbacks and steps < limit:
            self.callbacks.pop(0)()
            steps += 1


# Run choose_path on "Linux" with injected choosers; returns the delivered results and the Tk calls
def run_choose_path(portal_chooser, tk_result="/tk/choice"):
    results = []
    tk_calls = []
    scheduler = ManualScheduler()

    # Stand-in for the Tk dialog: records the call and returns a fixed path
    def tk_chooser(kind):
        tk_calls.append(kind)
        return tk_result

    # Run the background work immediately so the test needs no threads
    choose_path(
        DialogKind.TORRENT_FILE, "Pick", results.append, scheduler, tk_chooser,
        portal_chooser=portal_chooser, is_linux=True, run_in_background=lambda work: work(),
    )
    scheduler.run_until_idle()
    return results, tk_calls


# The torrent picker offers a *.torrent filter first, then everything
def test_build_options_torrent_filters():
    options = build_open_file_options(DialogKind.TORRENT_FILE, "meerko_abc")
    assert options["filters"] == ("a(sa(us))", [("Torrent files", [(0, "*.torrent")]), ("All files", [(0, "*")])])
    assert "directory" not in options


# The save picker asks the portal for folder mode
def test_build_options_folder_mode():
    options = build_open_file_options(DialogKind.SAVE_FOLDER, "meerko_abc")
    assert options["directory"] == ("b", True)
    assert "filters" not in options


# Every request carries its token and is modal
def test_options_include_token_and_modal():
    options = build_open_file_options(DialogKind.SAVE_FOLDER, "meerko_abc")
    assert options["handle_token"] == ("s", "meerko_abc")
    assert options["modal"] == ("b", True)


# The response object path is derived from our unique bus name per the portal spec
def test_request_path_escapes_sender():
    assert request_path(":1.42", "tok") == "/org/freedesktop/portal/desktop/request/1_42/tok"


# Percent-encoding and the localhost form are decoded into normal paths (Review Focus 3)
@pytest.mark.parametrize(
    ("uri", "expected"),
    [
        ("file:///home/u/a.torrent", "/home/u/a.torrent"),
        ("file:///home/u/My%20Torrents/%C3%A9.torrent", "/home/u/My Torrents/é.torrent"),
        ("file://localhost/x", "/x"),
    ],
)
def test_uri_to_path_decodes(uri, expected):
    assert uri_to_path(uri) == expected


# Anything that is not a local file is refused (Review Focus 4)
@pytest.mark.parametrize("uri", ["http://h/x", "smb://h/x", "file://otherhost/x", "file:relative", ""])
def test_uri_to_path_rejects_non_local(uri):
    assert uri_to_path(uri) is None


# Cancel (1) and other failures (2) give None; success gives the first chosen path (Review Focus 1)
def test_cancelled_response_returns_none():
    assert response_to_path(1, {}) is None
    assert response_to_path(2, {}) is None
    chosen = {"uris": ("as", ["file:///a.torrent", "file:///b.torrent"])}
    assert response_to_path(0, chosen) == "/a.torrent"
    assert response_to_path(0, {}) is None


# Without a session bus there is no portal to talk to
def test_missing_session_bus_is_portal_unavailable(monkeypatch):
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    with pytest.raises(PortalUnavailable):
        file_dialogs.portal_open_file(DialogKind.TORRENT_FILE, "Pick")


# A portal that never answers the method call becomes "unavailable", not a frozen dialog (Review Focus 2)
def test_method_timeout_is_portal_unavailable(monkeypatch):
    pytest.importorskip("jeepney")
    import jeepney.io.blocking

    # Simulate a bus that accepts the connection attempt but times out
    def hanging_connection(*_arguments, **_keywords):
        raise TimeoutError("no reply")

    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/nonexistent")
    monkeypatch.setattr(jeepney.io.blocking, "open_dbus_connection", hanging_connection)
    with pytest.raises(PortalUnavailable):
        file_dialogs.portal_open_file(DialogKind.TORRENT_FILE, "Pick", method_timeout=0.1)


# Off Linux the Tk dialog (the Explorer dialog on Windows) is used directly and synchronously
def test_choose_path_non_linux_uses_tk_directly():
    results = []

    # Portal must never be tried off Linux
    def forbidden_portal(kind, title):
        raise AssertionError("portal used off Linux")

    choose_path(
        DialogKind.SAVE_FOLDER, "Pick", results.append, ManualScheduler(), lambda kind: "C:/Downloads",
        portal_chooser=forbidden_portal, is_linux=False,
    )
    assert results == ["C:/Downloads"]


# A portal answer is delivered through the scheduler and the Tk dialog is not opened
def test_choose_path_linux_portal_result_delivered():
    results, tk_calls = run_choose_path(lambda kind, title: "/a.torrent")
    assert results == ["/a.torrent"]
    assert tk_calls == []


# A cancelled portal dialog delivers None without falling back to Tk
def test_choose_path_linux_cancel_delivers_none():
    results, tk_calls = run_choose_path(lambda kind, title: None)
    assert results == [None]
    assert tk_calls == []


# An unusable portal silently falls back to the Tk dialog
def test_choose_path_linux_falls_back_to_tk():
    # Simulates the user's current session: the portal cannot start
    def failing_portal(kind, title):
        raise PortalUnavailable("startup job failed")

    results, tk_calls = run_choose_path(failing_portal)
    assert results == ["/tk/choice"]
    assert tk_calls == [DialogKind.TORRENT_FILE]


# Scripted stand-in for a jeepney blocking connection to a portal; incoming signals are real jeepney messages
class FakePortalConnection:
    def __init__(self, jeepney, version=4, open_file_error=None, handle_suffix="", final_signal="response", uri=""):
        self.jeepney = jeepney
        self.unique_name = ":1.42"
        self.version = version
        self.open_file_error = open_file_error
        self.handle_suffix = handle_suffix
        self.final_signal = final_signal
        self.uri = uri
        self.filters = []
        self.incoming = []
        self.added_matches = []

    def __enter__(self):
        return self

    def __exit__(self, *exception_info):
        return False

    # Answer method calls by member name, the way the portal and bus would
    def send_and_get_reply(self, message, *, timeout=None, unwrap=None):
        member = message.header.fields[self.jeepney.HeaderFields.member]
        body = self.reply_body(member, message)
        # Proxy calls ask for an unwrapped body; direct calls get a message-like reply
        if unwrap:
            return body
        return type("Reply", (), {"header": type("Header", (), {"message_type": self.jeepney.MessageType.method_return}), "body": body})

    # Reply bodies per method; OpenFile also schedules the signal the portal would emit later
    def reply_body(self, member, message):
        if member == "AddMatch":
            self.added_matches.append(message.body[0])
            return ()
        if member == "Get":
            return (("u", self.version),)
        if self.open_file_error is not None:
            raise self.open_file_error
        token = message.body[2]["handle_token"][1]
        handle = request_path(self.unique_name, token) + self.handle_suffix
        self.incoming.append(self.build_final_signal(handle))
        return (handle,)

    # The Response on the handle path, or the portal leaving the bus
    def build_final_signal(self, handle):
        jeepney = self.jeepney
        if self.final_signal == "portal_gone":
            bus = jeepney.DBusAddress("/org/freedesktop/DBus", interface="org.freedesktop.DBus")
            return jeepney.new_signal(bus, "NameOwnerChanged", "sss", ("org.freedesktop.portal.Desktop", ":1.5", ""))
        request = jeepney.DBusAddress(handle, interface="org.freedesktop.portal.Request")
        return jeepney.new_signal(request, "Response", "ua{sv}", (0, {"uris": ("as", [self.uri])}))

    # Same contract as jeepney's filter(): a deque that matching incoming messages are appended to
    def filter(self, rule, *, queue=None, bufsize=1):
        import collections
        import contextlib

        matches = queue if queue is not None else collections.deque(maxlen=bufsize)
        self.filters.append((rule, matches))

        # Remove the filter again when the with-block ends
        @contextlib.contextmanager
        def scope():
            try:
                yield matches
            finally:
                self.filters.remove((rule, matches))

        return scope()

    # Deliver the next scripted message to every matching filter
    def recv_messages(self, *, timeout=None):
        if not self.incoming:
            raise AssertionError("waited for a message that will never come")
        message = self.incoming.pop(0)
        for rule, matches in self.filters:
            if rule.matches(message):
                matches.append(message)


# Run portal_open_file against a fake connection
def open_with_fake(monkeypatch, kind, **fake_options):
    jeepney = pytest.importorskip("jeepney")
    import jeepney.io.blocking

    connection = FakePortalConnection(jeepney, **fake_options)
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/fake")
    monkeypatch.setattr(jeepney.io.blocking, "open_dbus_connection", lambda **_keywords: connection)
    return file_dialogs.portal_open_file(kind, "Pick", method_timeout=0.1)


# The full success path: subscribe, ask, receive the Response, decode the URI
def test_portal_success_path(monkeypatch):
    chosen = open_with_fake(monkeypatch, DialogKind.TORRENT_FILE, uri="file:///x%20y.torrent")
    assert chosen == "/x y.torrent"


# Folder mode works on a new enough portal
def test_portal_folder_mode(monkeypatch):
    assert open_with_fake(monkeypatch, DialogKind.SAVE_FOLDER, version=4, uri="file:///home/u/dl") == "/home/u/dl"


# A portal without folder mode is unavailable for the save picker
def test_portal_too_old_for_folders(monkeypatch):
    with pytest.raises(PortalUnavailable):
        open_with_fake(monkeypatch, DialogKind.SAVE_FOLDER, version=2)


# OpenFile timing out falls back instead of freezing (Review Focus 2, at the method call)
def test_open_file_timeout_is_portal_unavailable(monkeypatch):
    with pytest.raises(PortalUnavailable):
        open_with_fake(monkeypatch, DialogKind.TORRENT_FILE, open_file_error=TimeoutError("no reply"))


# A portal that ignores our token answers on another path; we still get the answer (review I1)
def test_portal_ignoring_handle_token(monkeypatch):
    chosen = open_with_fake(monkeypatch, DialogKind.TORRENT_FILE, handle_suffix="_other", uri="file:///a.torrent")
    assert chosen == "/a.torrent"


# The portal leaving the bus mid-dialog ends the wait as a cancel instead of blocking forever (review I1)
def test_portal_disappearing_ends_wait(monkeypatch):
    assert open_with_fake(monkeypatch, DialogKind.TORRENT_FILE, final_signal="portal_gone") is None
