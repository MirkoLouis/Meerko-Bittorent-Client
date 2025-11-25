# Meerko vs. The BitTorrent Protocol

This document clarifies what the Meerko Bittorent Client is and how it relates to the underlying BitTorrent protocol.

## BitTorrent is the Protocol, Meerko is the Client

The most important distinction to understand is that **BitTorrent** is a **protocol**, not a piece of software. It is a set of rules and procedures that define how a decentralized, peer-to-peer network for file sharing should operate.

**Meerko Bittorent Client** is a software application—a **client**—that **implements** the BitTorrent protocol to download and upload files. In the same way that Chrome and Firefox are clients that use the HTTP protocol to browse the web, Meerko is a client that uses the BitTorrent protocol to participate in a torrent swarm.

## What Meerko Adds on Top of the Protocol

The BitTorrent protocol itself does not have opinions on user privacy or ease of use. It simply defines how peers should communicate. Meerko adds several layers of functionality and design choices on top of the bare protocol, primarily by configuring and orchestrating the powerful `libtorrent` library.

Here are the key features and characteristics that Meerko adds:

### 1. Focus on User Anonymity and Security

*   **Simplified Proxy Configuration:** The BitTorrent protocol itself does not specify how to hide a user's IP address. Meerko provides a simple, command-line interface to configure a proxy (like a SOCKS5 server).
*   **Secure Defaults:** When a proxy is used, Meerko configures `libtorrent` to force all traffic through it and enables "anonymous mode," which prevents the client from leaking its IP address in other ways (e.g., through peer exchange). This makes it much easier for a user to achieve a higher level of anonymity than if they were using a more basic client.

### 2. Simplicity and Abstraction

*   **Easy-to-Use CLI:** `libtorrent` is a complex library with hundreds of settings. Meerko provides a clean and simple command-line interface that exposes only the most essential features: specifying a torrent file, a save path, and optional proxy settings.
*   **Abstraction Layer:** The `MeerkoClient` class in `client.py` is an abstraction layer that handles the setup and management of the `libtorrent` session. A user of the client does not need to know the inner workings of `libtorrent` to download a file.

### 3. A Learning and Development Platform

*   **Python-based:** The client is written entirely in Python, a high-level and easy-to-read language. This makes it an excellent tool for anyone (especially an IT student) who wants to understand how a real BitTorrent client is built.
*   **Extensible:** Because it is written in Python and has a clear structure, it is easy to add new features or experiment with different settings of the `libtorrent` library.

In summary, Meerko doesn't change the BitTorrent protocol itself. Instead, it provides a user-friendly, security-conscious, and educational **implementation** of that protocol.
