# SPDX-License-Identifier: GPL-3.0-or-later
"""meerko-bittorent-cli: download one torrent from the command line using the shared engine.

Exit codes: 0 finished, 1 torrent/disk error, 2 usage/config error, 3 already running elsewhere, 130 interrupted.
"""

import argparse
import getpass
import logging
import os
import signal
import sys
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import TextIO

from meerko_bittorent import __version__
from meerko_bittorent.config import default_config_path, insecure_password_file, load_config
from meerko_bittorent.driver import Outcome, drive_download
from meerko_bittorent.engine import Engine, libtorrent_version
from meerko_bittorent.errors import AlreadyRunningError, InputError, MeerkoError, TorrentError
from meerko_bittorent.proxy import ProxyKind, ProxySettings, merge_proxy
from meerko_bittorent.sources import MAGNET_PREFIX, prepare_save_path, prepare_source
from meerko_bittorent.status import DownloadStatus, format_status

EXIT_FINISHED = 0
EXIT_TORRENT_ERROR = 1
EXIT_INPUT_ERROR = 2
EXIT_ALREADY_RUNNING = 3
EXIT_INTERRUPTED = 130
PASSWORD_ENVIRONMENT_VARIABLE = "MEERKO_PROXY_PASSWORD"
POLL_INTERVAL_SECONDS = 1.0
PIPED_REPORT_INTERVAL_SECONDS = 10.0


# Command-line interface definition; there is deliberately no --proxy-pass (argv leaks to history and ps)
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meerko-bittorent-cli",
        description="Download a torrent and seed it to a 1.0 share ratio.",
    )
    parser.add_argument("source", help="path to a .torrent file, or a magnet link")
    parser.add_argument("save_path", help="folder to save into (created if missing)")
    parser.add_argument("--config", help="use this config.ini instead of the per-user one")
    parser.add_argument("--proxy-type", choices=[kind.value for kind in ProxyKind])
    parser.add_argument("--proxy-host")
    parser.add_argument("--proxy-port", type=int)
    parser.add_argument("--proxy-user")
    parser.add_argument("--no-proxy", action="store_true", help="ignore any configured proxy for this run")
    parser.add_argument("--quiet", action="store_true", help="no progress output; errors are still shown")
    parser.add_argument(
        "--version",
        action="version",
        version=f"meerko-bittorent-cli {__version__} (libtorrent {libtorrent_version()})",
    )
    return parser


# Fill in a missing proxy password from config, then the environment, then an interactive prompt
def resolve_password(
    settings: ProxySettings,
    config_password: str | None,
    environ: Mapping[str, str],
    stdin_is_tty: bool,
    prompt: Callable[[str], str],
) -> ProxySettings:
    # Without a username no password is needed; an explicit password is kept
    if not settings.username or settings.password:
        return settings

    # 1. The password the user put in config.ini
    if config_password:
        return replace(settings, password=config_password)

    # 2. The environment, for scripts
    environment_password = environ.get(PASSWORD_ENVIRONMENT_VARIABLE)
    if environment_password:
        return replace(settings, password=environment_password)

    # 3. Ask, but only when someone is at a terminal
    if stdin_is_tty:
        return replace(settings, password=prompt(f"Password for proxy user {settings.username}: "))

    raise InputError(
        f"proxy user {settings.username!r} needs a password: put it in config.ini, "
        f"set {PASSWORD_ENVIRONMENT_VARIABLE}, or run from a terminal to be prompted"
    )


# Config proxy (if enabled) overridden field by field by the flags; --no-proxy wins
def effective_proxy(arguments: argparse.Namespace, config_path: Path) -> ProxySettings | None:
    # A direct connection needs nothing from config.ini, so a broken file must not block it
    if arguments.no_proxy:
        return None

    proxy_config = load_config(config_path)
    # Warn when a stored password is readable by other users
    if insecure_password_file(config_path):
        print(
            f"warning: {config_path} contains a proxy password and other users can read it; "
            f"run: chmod 600 '{config_path}'",
            file=sys.stderr,
        )

    base = proxy_config.settings if proxy_config.enabled else None
    # The password is resolved separately so its source order is always the same
    base_without_password = replace(base, password=None) if base is not None else None
    kind = ProxyKind(arguments.proxy_type) if arguments.proxy_type else None
    merged = merge_proxy(base_without_password, kind, arguments.proxy_host, arguments.proxy_port, arguments.proxy_user)

    # No proxy configured and none given on the command line
    if merged is None:
        return None

    merged.validate()
    # The stored password belongs to the stored proxy and user only; never send it anywhere else
    same_proxy_and_user = base_without_password is not None and merged == base_without_password
    config_password = base.password if same_proxy_and_user else None
    with_password = resolve_password(merged, config_password, os.environ, sys.stdin.isatty(), getpass.getpass)
    with_password.validate()
    return with_password


# Progress on stderr: one in-place line on a terminal, a plain line every 10 s when piped
class ProgressReporter:
    def __init__(self, stream: TextIO, is_terminal: bool, quiet: bool) -> None:
        self.stream = stream
        self.is_terminal = is_terminal
        self.quiet = quiet
        self.last_report_time: float | None = None
        self.line_open = False

    # Show one status snapshot, respecting quiet mode and the piped rate limit
    def report(self, status: DownloadStatus) -> None:
        if self.quiet:
            return
        line = format_status(status)
        # Terminal: overwrite the same line (padding clears leftovers from a longer previous line)
        if self.is_terminal:
            self.stream.write(f"\r{line:<100}")
            self.stream.flush()
            self.line_open = True
            return
        now = time.monotonic()
        # Piped: keep logs readable with one line per interval
        if self.last_report_time is None or now - self.last_report_time >= PIPED_REPORT_INTERVAL_SECONDS:
            self.stream.write(line + "\n")
            self.last_report_time = now

    # End the in-place line so later messages start on a fresh line
    def finish(self) -> None:
        if self.line_open:
            self.stream.write("\n")
            self.line_open = False


# Download, seed to ratio 1.0, and return the exit code; always closes the download
def run_download(
    arguments: argparse.Namespace,
    engine_factory: Callable[[ProxySettings | None], Engine],
    stop_event: threading.Event,
) -> int:
    config_path = Path(arguments.config).expanduser().resolve() if arguments.config else default_config_path()
    proxy = effective_proxy(arguments, config_path)
    source = prepare_source(arguments.source)
    save_path = prepare_save_path(arguments.save_path)

    engine = engine_factory(proxy)
    logging.info(engine.privacy_summary)
    reporter = ProgressReporter(sys.stderr, sys.stderr.isatty(), arguments.quiet)
    try:
        download = engine.start(source, save_path)
        # Remarks such as "no HTTP trackers" matter even in --quiet mode
        for note in download.notes:
            logging.warning(note)
        try:
            # Magnets first wait for their metadata inside the shared driver
            if source.startswith(MAGNET_PREFIX):
                logging.info("Fetching metadata...")
            outcome = drive_download(download, source, stop_event, reporter.report, POLL_INTERVAL_SECONDS)
        finally:
            download.close()
    finally:
        # End the progress line before any message, then quiet the session
        reporter.finish()
        engine.close()

    # Map the driver's outcome to an exit code
    if outcome is Outcome.FINISHED:
        logging.info("Finished: ratio 1.0 reached")
        return EXIT_FINISHED
    return EXIT_INTERRUPTED


# On POSIX, SIGTERM requests the same graceful stop as Ctrl+C; returns a function restoring the old handler
def install_termination_handler(stop_event: threading.Event) -> Callable[[], None]:
    # Signal handlers can only be installed from the main thread, and Windows has no SIGTERM delivery
    if os.name == "nt" or threading.current_thread() is not threading.main_thread():
        return lambda: None
    previous_handler = signal.signal(signal.SIGTERM, lambda _signal, _frame: stop_event.set())
    return lambda: signal.signal(signal.SIGTERM, previous_handler)


# Program entry for tests and main_entry(); returns the exit code instead of exiting
def main(
    argv: list[str] | None = None,
    engine_factory: Callable[[ProxySettings | None], Engine] = Engine,
    stop_event: threading.Event | None = None,
) -> int:
    try:
        arguments = build_parser().parse_args(argv)
    except SystemExit as exit_request:
        # argparse exits 2 on usage errors and 0 for --help/--version
        return int(exit_request.code or 0)

    logging.basicConfig(
        level=logging.WARNING if arguments.quiet else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )
    stop_event = stop_event if stop_event is not None else threading.Event()
    restore_handler = install_termination_handler(stop_event)
    try:
        return run_download(arguments, engine_factory, stop_event)
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
    except InputError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except AlreadyRunningError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_ALREADY_RUNNING
    except TorrentError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_TORRENT_ERROR
    except MeerkoError as error:
        # Any future subclass still ends cleanly
        print(f"error: {error}", file=sys.stderr)
        return EXIT_TORRENT_ERROR
    finally:
        restore_handler()


# Console-script entry point (meerko-bittorent-cli)
def main_entry() -> None:
    sys.exit(main())


if __name__ == "__main__":
    main_entry()
