# SPDX-License-Identifier: GPL-3.0-or-later
"""meerko-bittorent: the desktop window, a thin front-end over the shared engine.

form_to_proxy() and run_download_worker() hold the logic and never touch Tk, so they are unit-tested.
The worker thread talks to the window only through a queue; the Tk main thread drains it every 500 ms.
"""

import logging
import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, ttk

from meerko_bittorent.config import default_config_path, insecure_password_file, load_config, save_proxy_defaults
from meerko_bittorent.driver import Outcome, drive_download
from meerko_bittorent.engine import Engine
from meerko_bittorent.errors import AlreadyRunningError, InputError, MeerkoError
from meerko_bittorent.file_dialogs import DialogKind, choose_path
from meerko_bittorent.proxy import ProxyKind, ProxySettings, parse_proxy_kind, validate_port_text
from meerko_bittorent.sources import prepare_save_path, prepare_source
from meerko_bittorent.status import DownloadStatus, format_status

logger = logging.getLogger(__name__)

QUEUE_DRAIN_INTERVAL_MS = 500
WORKER_JOIN_TIMEOUT_SECONDS = 5.0
ALREADY_RUNNING_TEXT = "Already being downloaded by another Meerko process"
PROXY_TYPE_CHOICES = [kind.value for kind in ProxyKind]
ERROR_COLOUR = "#b00020"


# Messages from the worker thread to the window
@dataclass(frozen=True)
class StatusMessage:
    status: DownloadStatus


@dataclass(frozen=True)
class FinishedMessage:
    pass


@dataclass(frozen=True)
class StoppedMessage:
    pass


@dataclass(frozen=True)
class ErrorMessage:
    text: str


# Convert the proxy form into validated settings; None when the proxy box is unticked
def form_to_proxy(
    enabled: bool,
    kind_text: str,
    host: str,
    port_text: str,
    username: str,
    password: str,
    require_password: bool = True,
) -> ProxySettings | None:
    # Unticked means a direct connection, whatever the fields contain
    if not enabled:
        return None

    # Check fields in on-screen order so the message names the first thing to fix
    if not host.strip():
        raise InputError("Enter the proxy host")
    port = validate_port_text(port_text)

    settings = ProxySettings(
        kind=parse_proxy_kind(kind_text),
        host=host.strip(),
        port=port,
        username=username.strip() or None,
        password=password or None,
    )
    settings.validate()

    # The window cannot prompt mid-download, so a login needs its password up front
    if require_password and settings.username and not settings.password:
        raise InputError("Enter the proxy password for this user (it is never saved)")
    return settings


# The Tk dialogs: the native Explorer dialog on Windows, Tk's own dialog as the Linux fallback
def tk_chooser(kind: DialogKind) -> str | None:
    # Save locations are folders; sources are .torrent files
    if kind is DialogKind.SAVE_FOLDER:
        chosen = filedialog.askdirectory()
    else:
        chosen = filedialog.askopenfilename(filetypes=[("Torrent files", "*.torrent"), ("All files", "*.*")])
    # tkinter returns "" or () when cancelled
    return chosen if isinstance(chosen, str) and chosen else None


# Put a chosen path into its field; a cancelled chooser (None) leaves the field as it was
def apply_chosen_path(entry_setter, path: str | None) -> None:
    if path is None:
        return
    entry_setter(path)


# Body of the download thread: start, poll, and report through messages; never touches Tk
def run_download_worker(
    engine_factory,
    proxy: ProxySettings | None,
    source: str,
    save_path: Path,
    stop_event: threading.Event,
    messages: queue.Queue,
    poll_interval: float = 1.0,
) -> None:
    engine = None
    download = None
    try:
        engine = engine_factory(proxy)
        download = engine.start(source, save_path)
        outcome = drive_download(
            download, source, stop_event, lambda status: messages.put(StatusMessage(status)), poll_interval
        )
        # The final message tells the window how the download ended
        messages.put(FinishedMessage() if outcome is Outcome.FINISHED else StoppedMessage())
    except AlreadyRunningError:
        messages.put(ErrorMessage(ALREADY_RUNNING_TEXT))
    except MeerkoError as error:
        messages.put(ErrorMessage(str(error)))
    except Exception as error:
        # A bug must never leave the window stuck in "running"
        logger.exception("Unexpected error in the download worker")
        messages.put(ErrorMessage(f"unexpected error: {error}"))
    finally:
        # Always give the torrent and its lock back, then quiet the session
        if download is not None:
            download.close()
        if engine is not None:
            engine.close()


# The main window
class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Meerko Bittorent Client")
        self.geometry("470x540")
        self.config_path = default_config_path()
        self.messages: queue.Queue = queue.Queue()
        self.stop_event: threading.Event | None = None
        self.worker: threading.Thread | None = None
        # True from Start until the worker's final message; the thread may outlive this while it closes the session
        self.running = False

        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        self.build_source_rows(main_frame)
        self.build_proxy_frame(main_frame)
        self.build_action_row(main_frame)
        self.build_progress_frame(main_frame)

        self.load_defaults()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(QUEUE_DRAIN_INTERVAL_MS, self.drain_messages)

    # Torrent source and save folder, each with a Browse button
    def build_source_rows(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Torrent Source (file or magnet):").grid(row=0, column=0, sticky="w", pady=2)
        self.torrent_source_entry = ttk.Entry(parent, width=60)
        self.torrent_source_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=2)
        self.browse_torrent_button = ttk.Button(parent, text="Browse...", command=self.browse_torrent)
        self.browse_torrent_button.grid(row=1, column=2, sticky="w", padx=5)

        ttk.Label(parent, text="Save Path:").grid(row=2, column=0, sticky="w", pady=2)
        self.save_path_entry = ttk.Entry(parent, width=60)
        self.save_path_entry.grid(row=3, column=0, columnspan=2, sticky="ew", pady=2)
        self.browse_save_path_button = ttk.Button(parent, text="Browse...", command=self.browse_save_path)
        self.browse_save_path_button.grid(row=3, column=2, sticky="w", padx=5)

    # Proxy fields, the enable box and the Save as default button
    def build_proxy_frame(self, parent: ttk.Frame) -> None:
        proxy_frame = ttk.LabelFrame(parent, text="Proxy Settings", padding="10")
        proxy_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=10)

        self.proxy_enabled = tk.BooleanVar()
        self.proxy_check = ttk.Checkbutton(
            proxy_frame, text="Enable Proxy", variable=self.proxy_enabled, command=self.update_proxy_field_states
        )
        self.proxy_check.grid(row=0, column=0, columnspan=2, sticky="w")

        ttk.Label(proxy_frame, text="Type:").grid(row=1, column=0, sticky="w", pady=2)
        self.proxy_type_combobox = ttk.Combobox(proxy_frame, values=PROXY_TYPE_CHOICES, state="readonly")
        self.proxy_type_combobox.set(ProxyKind.SOCKS5.value)
        self.proxy_type_combobox.grid(row=1, column=1, sticky="ew", pady=2)

        self.proxy_host_entry = self.add_labelled_entry(proxy_frame, "Host:", 2)
        self.proxy_port_entry = self.add_labelled_entry(proxy_frame, "Port:", 3)
        self.proxy_user_entry = self.add_labelled_entry(proxy_frame, "Username:", 4)
        self.proxy_pass_entry = self.add_labelled_entry(proxy_frame, "Password:", 5, show="*")

        self.save_defaults_button = ttk.Button(proxy_frame, text="Save as default", command=self.save_defaults)
        self.save_defaults_button.grid(row=6, column=1, sticky="e", pady=(6, 0))

    # One label + entry row in the proxy frame
    def add_labelled_entry(self, parent: ttk.LabelFrame, label: str, row: int, show: str = "") -> ttk.Entry:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        entry = ttk.Entry(parent, show=show)
        entry.grid(row=row, column=1, sticky="ew", pady=2)
        return entry

    # Start and Stop buttons
    def build_action_row(self, parent: ttk.Frame) -> None:
        action_frame = ttk.Frame(parent)
        action_frame.grid(row=5, column=0, columnspan=3, pady=10)
        self.start_button = ttk.Button(action_frame, text="Start Download", command=self.start_download)
        self.start_button.pack(side="left", padx=5)
        self.stop_button = ttk.Button(action_frame, text="Stop", command=self.stop_download, state="disabled")
        self.stop_button.pack(side="left", padx=5)

    # Status line and progress bar
    def build_progress_frame(self, parent: ttk.Frame) -> None:
        progress_frame = ttk.LabelFrame(parent, text="Progress", padding="10")
        progress_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=10)
        self.progress_label = ttk.Label(progress_frame, text="Status: Idle", wraplength=420)
        self.progress_label.pack(fill=tk.X)
        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=100, mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=5)

    # Normal status text
    def show_status(self, text: str) -> None:
        self.progress_label.config(text=text, foreground="")

    # Error text in red
    def show_error(self, text: str) -> None:
        self.progress_label.config(text=text, foreground=ERROR_COLOUR)

    # Replace an entry's text
    def set_entry_text(self, entry: ttk.Entry, text: str) -> None:
        entry.delete(0, tk.END)
        entry.insert(0, text)

    # Pre-fill the proxy fields from the per-user config.ini
    def load_defaults(self) -> None:
        try:
            proxy_config = load_config(self.config_path)
        except InputError as error:
            self.show_error(f"Config: {error}")
            self.update_proxy_field_states()
            return

        settings = proxy_config.settings
        # Fill whatever is stored, even when the proxy is switched off
        if settings is not None:
            self.proxy_type_combobox.set(settings.kind.value)
            self.set_entry_text(self.proxy_host_entry, settings.host)
            self.set_entry_text(self.proxy_port_entry, str(settings.port))
            self.set_entry_text(self.proxy_user_entry, settings.username or "")
            self.set_entry_text(self.proxy_pass_entry, settings.password or "")
        self.proxy_enabled.set(proxy_config.enabled and settings is not None)
        self.update_proxy_field_states()

        # A stored password readable by other users deserves a visible warning
        if insecure_password_file(self.config_path):
            self.show_error(f"Warning: {self.config_path} holds a password other users can read (chmod 600 it)")

    # Proxy fields are editable only when the proxy is enabled and nothing is running
    def update_proxy_field_states(self) -> None:
        entry_state = "normal" if self.proxy_enabled.get() and not self.running else "disabled"
        # Every plain entry follows the same state
        for entry in (self.proxy_host_entry, self.proxy_port_entry, self.proxy_user_entry, self.proxy_pass_entry):
            entry.config(state=entry_state)
        self.proxy_type_combobox.config(state="readonly" if entry_state == "normal" else "disabled")

    # Lock or unlock the whole form around a running download
    def set_running(self, running: bool) -> None:
        self.running = running
        idle_state = "disabled" if running else "normal"
        # Inputs that must not change mid-download
        for widget in (
            self.torrent_source_entry,
            self.save_path_entry,
            self.browse_torrent_button,
            self.browse_save_path_button,
            self.proxy_check,
            self.save_defaults_button,
            self.start_button,
        ):
            widget.config(state=idle_state)
        self.stop_button.config(state="normal" if running else "disabled")
        self.update_proxy_field_states()

    # File picker for .torrent files (desktop chooser on Linux, Explorer on Windows)
    def browse_torrent(self) -> None:
        self.open_chooser(DialogKind.TORRENT_FILE, "Choose a torrent file", self.torrent_source_entry)

    # Folder picker for the save location
    def browse_save_path(self) -> None:
        self.open_chooser(DialogKind.SAVE_FOLDER, "Choose where to save", self.save_path_entry)

    # Open a chooser without blocking the window; Browse stays disabled until it answers
    def open_chooser(self, kind: DialogKind, title: str, target_entry: ttk.Entry) -> None:
        self.set_browse_buttons_state("disabled")

        # Runs on the Tk thread once the user has chosen or cancelled
        def on_result(path: str | None) -> None:
            # A download that started meanwhile keeps the form locked
            if not self.running:
                self.set_browse_buttons_state("normal")
            apply_chosen_path(lambda text: self.set_entry_text(target_entry, text), path)

        choose_path(kind, title, on_result, self.after, tk_chooser)

    # Enable or disable both Browse buttons together
    def set_browse_buttons_state(self, state: str) -> None:
        self.browse_torrent_button.config(state=state)
        self.browse_save_path_button.config(state=state)

    # Proxy settings from the form; raises InputError
    def proxy_from_form(self, require_password: bool) -> ProxySettings | None:
        return form_to_proxy(
            self.proxy_enabled.get(),
            self.proxy_type_combobox.get(),
            self.proxy_host_entry.get(),
            self.proxy_port_entry.get(),
            self.proxy_user_entry.get(),
            self.proxy_pass_entry.get(),
            require_password=require_password,
        )

    # Validate the form, then start the worker thread
    def start_download(self) -> None:
        raw_source = self.torrent_source_entry.get().strip()
        raw_save_path = self.save_path_entry.get().strip()
        # Both fields are required before anything else is checked
        if not raw_source or not raw_save_path:
            self.show_error("Torrent source and save path are required.")
            return

        try:
            proxy = self.proxy_from_form(require_password=True)
            source = prepare_source(raw_source)
            save_path = prepare_save_path(raw_save_path)
        except InputError as error:
            self.show_error(str(error))
            return

        self.stop_event = threading.Event()
        self.worker = threading.Thread(
            target=run_download_worker,
            args=(Engine, proxy, source, save_path, self.stop_event, self.messages),
            daemon=True,
        )
        self.worker.start()
        self.progress_bar["value"] = 0
        self.show_status("Starting...")
        self.set_running(True)

    # Ask the worker to stop; it reports StoppedMessage when done
    def stop_download(self) -> None:
        if self.stop_event is not None:
            self.stop_event.set()
            self.show_status("Stopping...")

    # Save the proxy fields as the default for both front-ends (never the password)
    def save_defaults(self) -> None:
        enabled = self.proxy_enabled.get()
        try:
            # With an empty host there is no endpoint to store, only the on/off state
            if not self.proxy_host_entry.get().strip():
                settings = None
            else:
                settings = form_to_proxy(
                    True,
                    self.proxy_type_combobox.get(),
                    self.proxy_host_entry.get(),
                    self.proxy_port_entry.get(),
                    self.proxy_user_entry.get(),
                    "",
                    require_password=False,
                )
            save_proxy_defaults(self.config_path, enabled and settings is not None, settings)
        except (InputError, OSError) as error:
            self.show_error(f"Could not save: {error}")
            return
        self.show_status(f"Saved proxy defaults to {self.config_path} (password not saved)")

    # Handle one worker message on the Tk thread
    def handle_message(self, message: object) -> None:
        if isinstance(message, StatusMessage):
            self.progress_bar["value"] = message.status.progress * 100
            self.show_status(format_status(message.status))
            return

        # Every other message ends the download
        self.set_running(False)
        if isinstance(message, FinishedMessage):
            self.show_status("Finished — ratio 1.0 reached")
        elif isinstance(message, StoppedMessage):
            self.show_status("Stopped")
        elif isinstance(message, ErrorMessage):
            self.show_error(f"Error: {message.text}")

    # Apply all queued worker messages, then schedule the next check
    def drain_messages(self) -> None:
        # Empty the queue completely each tick so the display never lags behind
        while True:
            try:
                message = self.messages.get_nowait()
            except queue.Empty:
                break
            self.handle_message(message)
        self.after(QUEUE_DRAIN_INTERVAL_MS, self.drain_messages)

    # Closing the window stops a running download first (torrent removed, lock released)
    def on_close(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            self.stop_event.set()
            self.worker.join(timeout=WORKER_JOIN_TIMEOUT_SECONDS)
        self.destroy()


# Keep "python meerko_bittorent/ui.py" working during development
if __name__ == "__main__":
    App().mainloop()
