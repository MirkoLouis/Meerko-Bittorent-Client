# SPDX-License-Identifier: GPL-3.0-or-later
"""The per-user config.ini shared by the CLI and the GUI.

Location: $XDG_CONFIG_HOME/meerko-bittorent/config.ini (default ~/.config/...) on Linux,
%APPDATA%\\meerko-bittorent\\config.ini on Windows. The app never writes a proxy password to it.
"""

import configparser
import io
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from meerko_bittorent.errors import InputError
from meerko_bittorent.proxy import ProxySettings, parse_proxy_kind

APPLICATION_DIRECTORY = "meerko-bittorent"
CONFIG_FILE_NAME = "config.ini"
PROXY_SECTION = "Proxy"
# Keys that describe where the proxy is; without them a disabled section means "no proxy"
ENDPOINT_KEYS = ("type", "host", "port")
PRIVATE_FILE_MODE = 0o600
GROUP_AND_OTHER_PERMISSIONS = 0o077


# Whether the proxy is switched on, and which proxy
@dataclass(frozen=True)
class ProxyConfig:
    enabled: bool
    settings: ProxySettings | None


# Absolute path of the per-user config file; arguments exist so tests can simulate other platforms
def default_config_path(is_windows: bool | None = None, environ: Mapping[str, str] | None = None) -> Path:
    base_directory = user_base_directory("XDG_CONFIG_HOME", ".config", "APPDATA", is_windows, environ)
    return base_directory / APPLICATION_DIRECTORY / CONFIG_FILE_NAME


# A per-user base folder: the Windows variable on Windows, else an absolute XDG variable, else ~/<home_fallback>
def user_base_directory(
    xdg_variable: str,
    home_fallback: str,
    windows_variable: str,
    is_windows: bool | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    environment = os.environ if environ is None else environ
    running_on_windows = os.name == "nt" if is_windows is None else is_windows

    # Windows keeps per-user application data under %APPDATA% / %LOCALAPPDATA%
    if running_on_windows:
        return Path(environment[windows_variable])

    # The XDG spec says to ignore a relative value
    xdg_directory = environment.get(xdg_variable, "")
    if xdg_directory and Path(xdg_directory).is_absolute():
        return Path(xdg_directory)

    return Path(environment["HOME"]) / home_fallback


# Parse the file strictly (duplicate sections/keys are errors); every failure names the file
def read_config_parser(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(strict=True, interpolation=None)

    # A missing file is an empty configuration
    if not path.exists():
        return parser

    try:
        text = path.read_bytes().decode("utf-8")
        parser.read_string(text, source=str(path))
    except UnicodeDecodeError:
        raise InputError(f"{path}: the config file is not valid UTF-8 text") from None
    except configparser.Error as error:
        raise InputError(f"{path}: {error}") from None
    except OSError as error:
        raise InputError(f"{path}: cannot read the config file ({error.strerror})") from None
    return parser


# Read a required key from the [Proxy] section
def required_value(section: configparser.SectionProxy, key: str, path: Path) -> str:
    value = section.get(key, "").strip()
    # Missing and empty are the same problem for the user
    if not value:
        raise InputError(f"{path}: [{PROXY_SECTION}] is missing '{key}'")
    return value


# Convert the [Proxy] section into validated settings
def parse_proxy_section(section: configparser.SectionProxy, path: Path) -> ProxyConfig:
    try:
        enabled = section.getboolean("enabled", fallback=True)
    except ValueError:
        raise InputError(f"{path}: 'enabled' must be true or false") from None

    # A switched-off proxy with no endpoint stored is simply "no proxy" (what Save writes for an empty form)
    has_endpoint = any(section.get(key, "").strip() for key in ENDPOINT_KEYS)
    if not enabled and not has_endpoint:
        return ProxyConfig(False, None)

    port_text = required_value(section, "port", path)
    # Ports are whole numbers; anything else is a typo in the file
    if not port_text.isdigit():
        raise InputError(f"{path}: 'port' must be a number, got {port_text!r}")

    try:
        settings = ProxySettings(
            kind=parse_proxy_kind(required_value(section, "type", path)),
            host=required_value(section, "host", path),
            port=int(port_text),
            username=section.get("username", "").strip() or None,
            password=section.get("password", "") or None,
        )
        settings.validate()
    except InputError as error:
        # Prefix the file so the user knows where to fix it
        if str(path) in str(error):
            raise
        raise InputError(f"{path}: {error}") from None
    return ProxyConfig(enabled, settings)


# Load the proxy configuration; a missing file or section means no proxy
def load_config(path: Path) -> ProxyConfig:
    parser = read_config_parser(path)
    # No [Proxy] section: nothing configured
    if not parser.has_section(PROXY_SECTION):
        return ProxyConfig(False, None)
    return parse_proxy_section(parser[PROXY_SECTION], path)


# Write text to path, creating the file private to the user on POSIX
def write_private_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    # Windows has no POSIX modes; the per-user profile directory is already private
    if os.name == "nt":
        path.write_text(text, encoding="utf-8")
        return

    file_descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, PRIVATE_FILE_MODE)
    with os.fdopen(file_descriptor, "w", encoding="utf-8") as config_file:
        config_file.write(text)
    # O_CREAT's mode does not apply to an existing file, so tighten it explicitly
    os.chmod(path, PRIVATE_FILE_MODE)


# Save the proxy as the default for both front-ends; never writes the password, keeps a hand-written one
def save_proxy_defaults(path: Path, enabled: bool, settings: ProxySettings | None) -> None:
    parser = read_config_parser(path)
    existing_section = parser[PROXY_SECTION] if parser.has_section(PROXY_SECTION) else {}
    hand_written_password = existing_section.get("password")
    existing_username = existing_section.get("username", "").strip() or None

    # Rebuild the section from scratch so stale keys do not linger
    if parser.has_section(PROXY_SECTION):
        parser.remove_section(PROXY_SECTION)
    parser.add_section(PROXY_SECTION)
    section = parser[PROXY_SECTION]
    # A proxy cannot be on without an endpoint
    section["enabled"] = "true" if enabled and settings is not None else "false"

    # Store the endpoint even when disabled, so re-enabling needs no retyping
    if settings is not None:
        section["type"] = settings.kind.value
        section["host"] = settings.host
        section["port"] = str(settings.port)
        # Username is optional
        if settings.username:
            section["username"] = settings.username

    # A hand-written password is kept only while it still belongs to the same username
    new_username = settings.username if settings is not None else None
    if hand_written_password and new_username is not None and new_username == existing_username:
        section["password"] = hand_written_password

    # Serialize with configparser itself, then write with private permissions
    serialized = io.StringIO()
    parser.write(serialized)
    write_private_file(path, serialized.getvalue())


# True when the file holds a password and other users can read it (always False on Windows)
def insecure_password_file(path: Path) -> bool:
    # Windows ACLs are per-user by default under %APPDATA%; POSIX modes do not apply
    if os.name == "nt" or not path.exists():
        return False

    try:
        parser = read_config_parser(path)
    except InputError:
        return False

    has_password = parser.has_section(PROXY_SECTION) and bool(parser[PROXY_SECTION].get("password"))
    return has_password and bool(path.stat().st_mode & GROUP_AND_OTHER_PERMISSIONS)
