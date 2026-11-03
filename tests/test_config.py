# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the per-user config file: location, loading, password-safe saving, permissions."""

import os
from pathlib import Path

import pytest

from meerko_bittorent.config import (
    ProxyConfig,
    default_config_path,
    insecure_password_file,
    load_config,
    save_proxy_defaults,
)
from meerko_bittorent.errors import InputError
from meerko_bittorent.proxy import ProxyKind, ProxySettings

posix_only = pytest.mark.skipif(os.name == "nt", reason="POSIX file permissions")


# Write a config file with the given text and return its path
def write_config(directory: Path, text: str) -> Path:
    path = directory / "config.ini"
    path.write_text(text, encoding="utf-8")
    return path


# XDG_CONFIG_HOME wins when it is an absolute path
def test_default_path_uses_xdg_config_home():
    environ = {"XDG_CONFIG_HOME": "/xdg", "HOME": "/home/u"}
    assert default_config_path(is_windows=False, environ=environ) == Path("/xdg/meerko-bittorent/config.ini")


# Without XDG_CONFIG_HOME (or with a relative one, which the XDG spec says to ignore) use ~/.config
def test_default_path_falls_back_to_home_config():
    expected = Path("/home/u/.config/meerko-bittorent/config.ini")
    assert default_config_path(is_windows=False, environ={"HOME": "/home/u"}) == expected
    relative_xdg = {"XDG_CONFIG_HOME": "relative", "HOME": "/home/u"}
    assert default_config_path(is_windows=False, environ=relative_xdg) == expected


# Windows uses %APPDATA%
def test_default_path_windows_appdata():
    environ = {"APPDATA": "/fake/appdata"}
    assert default_config_path(is_windows=True, environ=environ) == Path("/fake/appdata/meerko-bittorent/config.ini")


# No file means no proxy
def test_missing_file_means_no_proxy(tmp_path):
    assert load_config(tmp_path / "absent.ini") == ProxyConfig(False, None)


# Every key is read into the settings
def test_load_full_section(tmp_path):
    path = write_config(
        tmp_path,
        "[Proxy]\nenabled = true\ntype = socks5\nhost = proxy.example\nport = 1080\n"
        "username = me\npassword = secret\n",
    )
    expected = ProxySettings(ProxyKind.SOCKS5, "proxy.example", 1080, "me", "secret")
    assert load_config(path) == ProxyConfig(True, expected)


# Old config files have no "enabled" key; a [Proxy] section means enabled
def test_enabled_defaults_true_when_section_present(tmp_path):
    path = write_config(tmp_path, "[Proxy]\ntype = http\nhost = h\nport = 8080\n")
    assert load_config(path).enabled is True


# Corrupted files fail with a message naming the file instead of crashing
@pytest.mark.parametrize(
    "content",
    [
        "[Proxy]\ntype = socks5\nhost = h\nport = abc\n",
        "[Proxy]\ntype = socks4\nhost = h\nport = 1080\n",
        b"\xff\xfe[Proxy]\n",
        "[Proxy]\nhost = h\n[Proxy]\nhost = i\n",
        "[Proxy]\ntype = socks5\nport = 1080\n",
        "[Proxy]\nenabled = maybe\ntype = socks5\nhost = h\nport = 1080\n",
    ],
)
def test_malformed_config_raises_input_error(tmp_path, content):
    path = tmp_path / "config.ini"
    # Bytes exercise the non-UTF-8 case; text covers the value errors
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    with pytest.raises(InputError, match=str(path)):
        load_config(path)


# The app never writes the password to disk
def test_save_never_writes_password(tmp_path):
    path = tmp_path / "config.ini"
    save_proxy_defaults(path, True, ProxySettings(ProxyKind.SOCKS5, "h", 1080, "me", "secret"))
    text = path.read_text(encoding="utf-8")
    assert "secret" not in text
    assert "password" not in text
    assert load_config(path) == ProxyConfig(True, ProxySettings(ProxyKind.SOCKS5, "h", 1080, "me"))


# A password the user typed into the file by hand survives a save
def test_save_keeps_hand_written_password(tmp_path):
    path = write_config(tmp_path, "[Proxy]\ntype = socks5\nhost = old\nport = 1\nusername = me\npassword = keep\n")
    save_proxy_defaults(path, True, ProxySettings(ProxyKind.HTTP, "new", 8080, "me", "typed-in-gui"))
    loaded = load_config(path)
    assert loaded.settings == ProxySettings(ProxyKind.HTTP, "new", 8080, "me", "keep")


# Saving with the proxy disabled keeps the endpoint but turns it off
def test_save_disabled_keeps_endpoint(tmp_path):
    path = tmp_path / "config.ini"
    save_proxy_defaults(path, False, ProxySettings(ProxyKind.SOCKS5, "h", 1080))
    assert load_config(path) == ProxyConfig(False, ProxySettings(ProxyKind.SOCKS5, "h", 1080))


# The directory is created and the file is private to the user
@posix_only
def test_save_creates_directory_and_0600_file(tmp_path):
    path = tmp_path / "nested" / "config.ini"
    save_proxy_defaults(path, True, ProxySettings(ProxyKind.SOCKS5, "h", 1080))
    assert path.stat().st_mode & 0o777 == 0o600


# Only a password in a file other users can read is insecure
@posix_only
def test_insecure_password_file(tmp_path):
    with_password = write_config(tmp_path, "[Proxy]\ntype = socks5\nhost = h\nport = 1\nusername = u\npassword = p\n")
    with_password.chmod(0o644)
    assert insecure_password_file(with_password) is True
    with_password.chmod(0o600)
    assert insecure_password_file(with_password) is False

    without_password = tmp_path / "other.ini"
    without_password.write_text("[Proxy]\ntype = socks5\nhost = h\nport = 1\n", encoding="utf-8")
    without_password.chmod(0o644)
    assert insecure_password_file(without_password) is False
    assert insecure_password_file(tmp_path / "absent.ini") is False
