# SPDX-License-Identifier: GPL-3.0-or-later
"""File and folder pickers: the desktop's own chooser on Linux (XDG Desktop Portal), Tk elsewhere or as fallback.

On Windows tkinter's filedialog already is the native Explorer dialog. On Linux the portal request runs on a
background thread so the Tk event loop keeps redrawing; the answer is handed back through a queue that the
caller's scheduler (tkinter's after()) polls. jeepney is imported only on the Linux portal path.
"""

import logging
import os
import queue
import secrets
import sys
import threading
from collections.abc import Callable
from enum import Enum
from urllib.parse import unquote, urlsplit

logger = logging.getLogger(__name__)

PORTAL_SERVICE = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
FILE_CHOOSER_INTERFACE = "org.freedesktop.portal.FileChooser"
REQUEST_INTERFACE = "org.freedesktop.portal.Request"
FOLDER_MODE_MINIMUM_VERSION = 3
DEFAULT_METHOD_TIMEOUT_SECONDS = 5.0
POLL_INTERVAL_MS = 100
RESPONSE_SUCCESS = 0
TORRENT_FILTERS = [("Torrent files", [(0, "*.torrent")]), ("All files", [(0, "*")])]


# The portal cannot be used; callers fall back to the Tk dialog
class PortalUnavailable(Exception):
    pass


# What the user is asked to choose
class DialogKind(Enum):
    TORRENT_FILE = "torrent_file"
    SAVE_FOLDER = "save_folder"


# OpenFile options as a jeepney a{sv} dict: {name: (signature, value)}
def build_open_file_options(kind: DialogKind, token: str) -> dict[str, tuple[str, object]]:
    options: dict[str, tuple[str, object]] = {"handle_token": ("s", token), "modal": ("b", True)}
    # Folders use the portal's directory mode; files get the *.torrent filter
    if kind is DialogKind.SAVE_FOLDER:
        options["directory"] = ("b", True)
    else:
        options["filters"] = ("a(sa(us))", TORRENT_FILTERS)
    return options


# Object path where the portal emits the Response for our request (sender ":1.42" → "1_42")
def request_path(unique_name: str, token: str) -> str:
    sender = unique_name.lstrip(":").replace(".", "_")
    return f"{PORTAL_PATH}/request/{sender}/{token}"


# Local absolute path for a file:// URI on this machine; anything else is refused
def uri_to_path(uri: str) -> str | None:
    parts = urlsplit(uri)
    # Only local files: no other schemes, no remote hosts
    if parts.scheme != "file" or parts.netloc not in ("", "localhost"):
        return None
    path = unquote(parts.path)
    # A relative "file:" path cannot be trusted to mean anything specific
    if not path.startswith("/"):
        return None
    return path


# Path chosen in a portal Response signal: code 0 is success, 1 cancelled, 2 other failure
def response_to_path(code: int, results: dict) -> str | None:
    if code != RESPONSE_SUCCESS:
        return None
    uris = results.get("uris")
    # results values are (signature, value) variants
    if not uris or not uris[1]:
        return None
    return uri_to_path(uris[1][0])


# Ask the portal's FileChooser and block until the user answers; raises PortalUnavailable if it cannot be used
def portal_open_file(
    kind: DialogKind, title: str, method_timeout: float = DEFAULT_METHOD_TIMEOUT_SECONDS
) -> str | None:
    # Without a session bus there is nothing to talk to
    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        raise PortalUnavailable("no D-Bus session bus")

    try:
        from jeepney import DBusAddress, MatchRule, message_bus, new_method_call
        from jeepney.io.blocking import Proxy, open_dbus_connection
        from jeepney.wrappers import DBusErrorResponse, unwrap_msg
    except ImportError as error:
        raise PortalUnavailable(f"jeepney is not installed: {error}") from None

    try:
        with open_dbus_connection(bus="SESSION") as connection:
            # Folder mode only exists from FileChooser version 3
            if kind is DialogKind.SAVE_FOLDER:
                properties = DBusAddress(PORTAL_PATH, bus_name=PORTAL_SERVICE, interface="org.freedesktop.DBus.Properties")
                version_call = new_method_call(properties, "Get", "ss", (FILE_CHOOSER_INTERFACE, "version"))
                version = unwrap_msg(connection.send_and_get_reply(version_call, timeout=method_timeout))[0][1]
                if version < FOLDER_MODE_MINIMUM_VERSION:
                    raise PortalUnavailable(f"FileChooser version {version} has no folder mode")

            # Subscribe to our Response before asking, so the answer cannot be missed
            token = f"meerko_{secrets.token_hex(8)}"
            response_rule = MatchRule(
                type="signal",
                interface=REQUEST_INTERFACE,
                member="Response",
                path=request_path(connection.unique_name, token),
            )
            Proxy(message_bus, connection, timeout=method_timeout).AddMatch(response_rule)

            with connection.filter(response_rule) as responses:
                chooser = DBusAddress(PORTAL_PATH, bus_name=PORTAL_SERVICE, interface=FILE_CHOOSER_INTERFACE)
                open_call = new_method_call(
                    chooser, "OpenFile", "ssa{sv}", ("", title, build_open_file_options(kind, token))
                )
                unwrap_msg(connection.send_and_get_reply(open_call, timeout=method_timeout))
                # The user may take as long as they like; no timeout here
                response = connection.recv_until_filtered(responses)
    except (DBusErrorResponse, OSError, TimeoutError, KeyError, IndexError, TypeError) as error:
        raise PortalUnavailable(f"desktop portal failed: {error}") from None

    code, results = response.body
    return response_to_path(code, results)


# Default background runner: a daemon thread, so an open dialog never blocks app exit
def start_daemon_thread(work: Callable[[], None]) -> None:
    threading.Thread(target=work, daemon=True).start()


# Ask the user for a path and call on_result(path or None) later on the caller's thread
def choose_path(
    kind: DialogKind,
    title: str,
    on_result: Callable[[str | None], None],
    schedule: Callable[[int, Callable[[], None]], object],
    tk_chooser: Callable[[DialogKind], str | None],
    portal_chooser: Callable[[DialogKind, str], str | None] = portal_open_file,
    is_linux: bool | None = None,
    run_in_background: Callable[[Callable[[], None]], None] = start_daemon_thread,
) -> None:
    running_on_linux = sys.platform.startswith("linux") if is_linux is None else is_linux

    # Windows/macOS: tkinter's dialog is already the native one
    if not running_on_linux:
        on_result(tk_chooser(kind))
        return

    answers: queue.Queue = queue.Queue(maxsize=1)

    # Background part: talk to the portal, or record that we must fall back
    def ask_portal() -> None:
        try:
            answers.put(("chosen", portal_chooser(kind, title)))
        except PortalUnavailable as error:
            logger.info("Using the built-in file dialog: %s", error)
            answers.put(("fallback", None))
        except Exception:
            logger.exception("Unexpected error from the desktop portal; using the built-in file dialog")
            answers.put(("fallback", None))

    # Caller-thread part: check for the answer every POLL_INTERVAL_MS
    def poll() -> None:
        try:
            outcome, path = answers.get_nowait()
        except queue.Empty:
            schedule(POLL_INTERVAL_MS, poll)
            return
        # The Tk dialog must open on the caller's (Tk) thread
        if outcome == "fallback":
            on_result(tk_chooser(kind))
            return
        on_result(path)

    run_in_background(ask_portal)
    schedule(POLL_INTERVAL_MS, poll)
