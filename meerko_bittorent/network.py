# SPDX-License-Identifier: GPL-3.0-or-later
"""Network policy: what Meerko may do on the network with no proxy, a SOCKS5 proxy or an HTTP proxy.

With a proxy the policy fails closed: anything that cannot go through the proxy is switched off rather than sent
directly. This module never imports libtorrent; enum-valued settings are given by name and converted by the engine.
"""

from enum import Enum

from meerko_bittorent.proxy import ProxyKind, ProxySettings

NO_HTTP_TRACKERS_NOTE = "No HTTP trackers: this torrent may find no peers through an HTTP proxy"
UDP_TRACKER_SCHEME = "udp://"

# The same for every profile: throughput tuning and "prefer encrypted, allow plain"
COMMON_SETTINGS: dict[str, object] = {
    "connections_limit": 1000,
    "choking_algorithm": "rate_based_choker",
    "send_buffer_watermark": 500 * 1024,
    "out_enc_policy": "pe_enabled",
    "in_enc_policy": "pe_enabled",
    "allowed_enc_level": "pe_both",
    "prefer_rc4": True,
}

# Route peers, trackers and host name lookups through the proxy
PROXY_ROUTING_SETTINGS: dict[str, object] = {
    "proxy_peer_connections": True,
    "proxy_tracker_connections": True,
    "proxy_hostnames": True,
}


# Which policy applies
class ProxyProfile(Enum):
    DIRECT = "direct"
    SOCKS5 = "socks5"
    HTTP = "http"


# Profile for an optional proxy
def proxy_profile(proxy: ProxySettings | None) -> ProxyProfile:
    if proxy is None:
        return ProxyProfile.DIRECT
    return ProxyProfile.SOCKS5 if proxy.kind is ProxyKind.SOCKS5 else ProxyProfile.HTTP


# Feature switches per profile (spec §2): router ports, LAN broadcast, DHT, uTP, identity hiding
PROFILE_SWITCHES: dict[ProxyProfile, dict[str, object]] = {
    ProxyProfile.DIRECT: {
        "enable_upnp": True,
        "enable_natpmp": True,
        "enable_lsd": True,
        "enable_dht": True,
        "enable_outgoing_utp": True,
        "enable_incoming_utp": True,
        "anonymous_mode": False,
        "dht_privacy_lookups": True,
    },
    ProxyProfile.SOCKS5: {
        "enable_upnp": False,
        "enable_natpmp": False,
        "enable_lsd": False,
        # SOCKS5 carries UDP (UDP ASSOCIATE), so DHT and uTP go through the proxy
        "enable_dht": True,
        "enable_outgoing_utp": True,
        "enable_incoming_utp": True,
        "anonymous_mode": True,
        "dht_privacy_lookups": True,
    },
    ProxyProfile.HTTP: {
        "enable_upnp": False,
        "enable_natpmp": False,
        "enable_lsd": False,
        # An HTTP proxy cannot carry UDP, so everything UDP-based is off
        "enable_dht": False,
        "enable_outgoing_utp": False,
        "enable_incoming_utp": False,
        "anonymous_mode": True,
    },
}

PRIVACY_SUMMARIES: dict[ProxyProfile, str] = {
    ProxyProfile.DIRECT: "Direct connection (no proxy)",
    ProxyProfile.SOCKS5: "SOCKS5 proxy: all traffic goes through the proxy",
    ProxyProfile.HTTP: "HTTP proxy: all traffic through the proxy; DHT, uTP and UDP trackers are off",
}


# Every network-related session setting for this proxy (or none)
def network_settings(proxy: ProxySettings | None) -> dict[str, object]:
    profile = proxy_profile(proxy)
    settings = dict(COMMON_SETTINGS)
    settings.update(PROFILE_SWITCHES[profile])
    # Proxy endpoint, login and routing only exist when there is a proxy
    if proxy is not None:
        settings.update(PROXY_ROUTING_SETTINGS)
        settings.update(proxy.to_libtorrent())
    return settings


# The one line shown to the user for the active mode
def privacy_summary(proxy: ProxySettings | None) -> str:
    return PRIVACY_SUMMARIES[proxy_profile(proxy)]


# Whether a tracker may be used: HTTP mode drops UDP trackers (they cannot go through the proxy)
def keeps_tracker(url: str, profile: ProxyProfile) -> bool:
    if profile is not ProxyProfile.HTTP:
        return True
    return not url.strip().lower().startswith(UDP_TRACKER_SCHEME)
