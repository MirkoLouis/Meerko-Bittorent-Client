# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the network policy: per-profile settings, summaries and tracker filtering (spec §2)."""

import pytest

from meerko_bittorent.network import (
    ProxyProfile,
    keeps_tracker,
    network_settings,
    privacy_summary,
    proxy_profile,
)
from meerko_bittorent.proxy import ProxyKind, ProxySettings

SOCKS5 = ProxySettings(ProxyKind.SOCKS5, "proxy.example", 1080)
SOCKS5_WITH_LOGIN = ProxySettings(ProxyKind.SOCKS5, "proxy.example", 1080, "me", "pw")
HTTP = ProxySettings(ProxyKind.HTTP, "proxy.example", 8080)
REMOVED_KEYS = ("force_proxy", "cache_size", "active_downloads", "active_seeds")
ENCRYPTION = {"out_enc_policy": "pe_enabled", "in_enc_policy": "pe_enabled", "allowed_enc_level": "pe_both", "prefer_rc4": True}
PERFORMANCE = {"connections_limit": 1000, "choking_algorithm": "rate_based_choker", "send_buffer_watermark": 512000}
PROXY_ROUTING = {"proxy_peer_connections": True, "proxy_tracker_connections": True, "proxy_hostnames": True}


# Assert that every expected key has exactly the expected value
def assert_subset(settings, expected):
    for key, value in expected.items():
        assert settings[key] == value, key


# No proxy: everything on for speed, identity not hidden, no proxy keys at all
def test_direct_profile_settings():
    settings = network_settings(None)
    assert_subset(settings, {
        "enable_upnp": True, "enable_natpmp": True, "enable_lsd": True, "enable_dht": True,
        "enable_outgoing_utp": True, "enable_incoming_utp": True,
        "anonymous_mode": False, "dht_privacy_lookups": True,
    })
    assert_subset(settings, ENCRYPTION)
    assert_subset(settings, PERFORMANCE)
    assert not any(key.startswith("proxy_") for key in settings)


# SOCKS5: no router ports, no LAN broadcast, DHT and uTP through the proxy, identity hidden
def test_socks5_profile_settings():
    settings = network_settings(SOCKS5)
    assert_subset(settings, {
        "enable_upnp": False, "enable_natpmp": False, "enable_lsd": False, "enable_dht": True,
        "enable_outgoing_utp": True, "enable_incoming_utp": True,
        "anonymous_mode": True, "dht_privacy_lookups": True, "proxy_type_name": "socks5",
    })
    assert_subset(settings, PROXY_ROUTING)
    assert_subset(settings, ENCRYPTION)


# HTTP: like SOCKS5, but nothing that needs UDP
def test_http_profile_settings():
    settings = network_settings(HTTP)
    assert_subset(settings, {
        "enable_upnp": False, "enable_natpmp": False, "enable_lsd": False, "enable_dht": False,
        "enable_outgoing_utp": False, "enable_incoming_utp": False,
        "anonymous_mode": True, "proxy_type_name": "http",
    })
    assert_subset(settings, PROXY_ROUTING)


# Deprecated or meaningless settings never come back
@pytest.mark.parametrize("proxy", [None, SOCKS5, HTTP])
def test_removed_settings_absent(proxy):
    settings = network_settings(proxy)
    assert not [key for key in REMOVED_KEYS if key in settings]


# A login only changes the proxy type to its authenticated variant (Review Focus 3)
def test_socks5_with_login_is_strict():
    with_login = network_settings(SOCKS5_WITH_LOGIN)
    without_login = network_settings(SOCKS5)
    assert proxy_profile(SOCKS5_WITH_LOGIN) is ProxyProfile.SOCKS5
    assert with_login["proxy_type_name"] == "socks5_pw"
    privacy_keys = [key for key in without_login if key.startswith("enable_") or key in PROXY_ROUTING]
    assert {key: with_login[key] for key in privacy_keys} == {key: without_login[key] for key in privacy_keys}


# The one line the user sees for each mode
def test_privacy_summary_texts():
    assert privacy_summary(None) == "Direct connection (no proxy)"
    assert privacy_summary(SOCKS5) == "SOCKS5 proxy: all traffic goes through the proxy"
    assert privacy_summary(HTTP) == "HTTP proxy: all traffic through the proxy; DHT, uTP and UDP trackers are off"


# Only HTTP mode drops UDP trackers, however the URL is written (Review Focus 1)
def test_keeps_tracker():
    for url in ("udp://t.example:80", "UDP://t.example:80", "  udp://t.example:80"):
        assert keeps_tracker(url, ProxyProfile.HTTP) is False
        assert keeps_tracker(url, ProxyProfile.SOCKS5) is True
        assert keeps_tracker(url, ProxyProfile.DIRECT) is True
    for url in ("http://t.example/announce", "https://t.example/announce", "wss://t.example/announce"):
        assert keeps_tracker(url, ProxyProfile.HTTP) is True
