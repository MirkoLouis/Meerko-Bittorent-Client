# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for proxy settings: validation, libtorrent mapping and field-by-field merging."""

import pytest

from meerko_bittorent.errors import InputError
from meerko_bittorent.proxy import ProxyKind, ProxySettings, merge_proxy, parse_proxy_kind, validate_port_text


@pytest.mark.parametrize(
    "settings",
    [
        ProxySettings(ProxyKind.SOCKS5, "", 1080),
        ProxySettings(ProxyKind.SOCKS5, "a b", 1080),
        ProxySettings(ProxyKind.SOCKS5, "host\n", 1080),
        ProxySettings(ProxyKind.SOCKS5, "host", 0),
        ProxySettings(ProxyKind.SOCKS5, "host", 65536),
        ProxySettings(ProxyKind.SOCKS5, "host", 1080, password="orphan"),
    ],
)
# Each invalid field is rejected with InputError
def test_validate_rejects(settings):
    with pytest.raises(InputError):
        settings.validate()


# The front-end resolves the password later, so a username alone is valid here
def test_validate_accepts_username_without_password():
    ProxySettings(ProxyKind.SOCKS5, "proxy.example", 1080, username="me").validate()


# A username switches to libtorrent's authenticated proxy variants
def test_to_libtorrent_picks_authenticated_types():
    socks_with_login = ProxySettings(ProxyKind.SOCKS5, "h", 1080, "me", "pw").to_libtorrent()
    http_with_login = ProxySettings(ProxyKind.HTTP, "h", 8080, "me", "pw").to_libtorrent()
    assert socks_with_login["proxy_type_name"] == "socks5_pw"
    assert http_with_login["proxy_type_name"] == "http_pw"
    assert socks_with_login["proxy_username"] == "me"
    assert socks_with_login["proxy_password"] == "pw"
    assert ProxySettings(ProxyKind.SOCKS5, "h", 1080).to_libtorrent()["proxy_type_name"] == "socks5"
    plain_http = ProxySettings(ProxyKind.HTTP, "h", 8080).to_libtorrent()
    assert plain_http == {"proxy_type_name": "http", "proxy_hostname": "h", "proxy_port": 8080}


# User-facing names parse case-insensitively; unsupported protocols are rejected
def test_parse_proxy_kind():
    assert parse_proxy_kind("SOCKS5") is ProxyKind.SOCKS5
    assert parse_proxy_kind("socks5_pw") is ProxyKind.SOCKS5
    assert parse_proxy_kind("http") is ProxyKind.HTTP
    with pytest.raises(InputError):
        parse_proxy_kind("socks4")


# A single flag changes only its own field
def test_merge_overrides_single_field():
    base = ProxySettings(ProxyKind.SOCKS5, "a", 1080, "me")
    merged = merge_proxy(base, None, None, 1081, None)
    assert merged == ProxySettings(ProxyKind.SOCKS5, "a", 1081, "me")


# Without a configured proxy, flags must describe a whole proxy
def test_merge_without_base_requires_kind_host_port():
    with pytest.raises(InputError):
        merge_proxy(None, ProxyKind.SOCKS5, "h", None, None)
    assert merge_proxy(None, None, None, None, None) is None
    assert merge_proxy(None, ProxyKind.HTTP, "h", 8080, None) == ProxySettings(ProxyKind.HTTP, "h", 8080)


EMPTY_PORT_MESSAGE = "Enter the proxy port (1–65535)"


# Each kind of bad port text gets its own message
@pytest.mark.parametrize(
    ("port_text", "expected"),
    [
        ("", EMPTY_PORT_MESSAGE),
        ("abc", "The proxy port must be a whole number from 1 to 65535 (you entered 'abc')"),
        ("-1", "The proxy port must be a whole number from 1 to 65535 (you entered '-1')"),
        ("0", "The proxy port must be between 1 and 65535 (you entered 0)"),
        ("70000", "The proxy port must be between 1 and 65535 (you entered 70000)"),
    ],
)
def test_validate_port_text_messages(port_text, expected):
    with pytest.raises(InputError) as raised:
        validate_port_text(port_text)
    assert str(raised.value) == expected


# Surrounding spaces are forgiven; spaces inside the number are not
def test_port_text_whitespace():
    assert validate_port_text(" 1080 ") == 1080
    with pytest.raises(InputError, match="whole number"):
        validate_port_text("10 80")


# Ports from config.ini or the CLI get the same range wording as the form
def test_settings_out_of_range_uses_range_message():
    with pytest.raises(InputError) as raised:
        ProxySettings(ProxyKind.SOCKS5, "h", 70000).validate()
    assert str(raised.value) == "The proxy port must be between 1 and 65535 (you entered 70000)"


# Unicode digits like "²" pass str.isdigit() but are not a port; they get the message, not a crash (review M1)
@pytest.mark.parametrize("port_text", ["²", "١٠٨٠", "1080²"])
def test_non_ascii_digits_get_whole_number_message(port_text):
    with pytest.raises(InputError, match="whole number"):
        validate_port_text(port_text)


# The password never appears when settings are printed or logged (Review Focus 5)
def test_repr_hides_password():
    settings = ProxySettings(ProxyKind.SOCKS5, "h", 1080, "me", "secret")
    assert "secret" not in repr(settings)
    assert "secret" not in f"{settings}"
    assert settings.password == "secret"
