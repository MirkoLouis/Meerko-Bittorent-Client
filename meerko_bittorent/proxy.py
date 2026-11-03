# SPDX-License-Identifier: GPL-3.0-or-later
"""Proxy settings shared by the CLI, the config file and the GUI.

This module never imports libtorrent: to_libtorrent() names the proxy type, and the engine converts it.
"""

from dataclasses import dataclass, replace
from enum import Enum

from meerko_bittorent.errors import InputError

MINIMUM_PORT = 1
MAXIMUM_PORT = 65535


# The proxy protocols a user can choose; login variants are derived from the username
class ProxyKind(Enum):
    SOCKS5 = "socks5"
    HTTP = "http"


# Accept the user-facing names, case-insensitively; "socks5_pw" is the legacy config spelling
def parse_proxy_kind(text: str) -> ProxyKind:
    normalized = text.strip().lower()
    # Older config files named the authenticated SOCKS5 variant explicitly
    if normalized == "socks5_pw":
        return ProxyKind.SOCKS5
    try:
        return ProxyKind(normalized)
    except ValueError:
        raise InputError(f"unsupported proxy type {text!r}; use socks5 or http") from None


# Reject host names with spaces or control characters (they cannot be valid and could break log output)
def has_invalid_host_characters(host: str) -> bool:
    return any(character.isspace() or not character.isprintable() for character in host)


# One proxy endpoint plus optional login
@dataclass(frozen=True)
class ProxySettings:
    kind: ProxyKind
    host: str
    port: int
    username: str | None = None
    password: str | None = None

    # Raise InputError describing the first problem found
    def validate(self) -> None:
        # Host must be present and plausible
        if not self.host:
            raise InputError("proxy host is empty")
        if has_invalid_host_characters(self.host):
            raise InputError(f"proxy host {self.host!r} contains spaces or control characters")

        # Port must be a real TCP port
        if not MINIMUM_PORT <= self.port <= MAXIMUM_PORT:
            raise InputError(f"proxy port {self.port} is outside {MINIMUM_PORT}-{MAXIMUM_PORT}")

        # A password only makes sense together with a username
        if self.password and not self.username:
            raise InputError("a proxy password was given without a username")

    # libtorrent settings for this proxy; "proxy_type_name" is a lt.proxy_type_t member name
    def to_libtorrent(self) -> dict[str, object]:
        type_name = self.kind.value
        settings: dict[str, object] = {"proxy_hostname": self.host, "proxy_port": self.port}

        # A username selects libtorrent's authenticated variant, which actually sends the login
        if self.username:
            type_name += "_pw"
            settings["proxy_username"] = self.username
            settings["proxy_password"] = self.password or ""

        settings["proxy_type_name"] = type_name
        return settings


# Apply field-by-field overrides (None = keep) on top of an optional base proxy
def merge_proxy(
    base: ProxySettings | None,
    kind: ProxyKind | None,
    host: str | None,
    port: int | None,
    username: str | None,
) -> ProxySettings | None:
    overrides = {"kind": kind, "host": host, "port": port, "username": username}
    given_overrides = {field: value for field, value in overrides.items() if value is not None}

    # Nothing configured and nothing given: no proxy
    if base is None and not given_overrides:
        return None

    # Overrides on an existing proxy change only their own fields
    if base is not None:
        return replace(base, **given_overrides)

    # Without a base, the overrides must describe a complete proxy
    if kind is None or host is None or port is None:
        raise InputError("a proxy needs --proxy-type, --proxy-host and --proxy-port when none is configured")
    return ProxySettings(kind, host, port, username)
