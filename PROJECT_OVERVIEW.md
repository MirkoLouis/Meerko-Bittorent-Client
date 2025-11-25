# Project Overview: Meerko Bittorent Client

## 1. Introduction

Meerko Bittorent is a BitTorrent client designed with three core principles in mind: user security, download speed, and performance. This document outlines the technical architecture and components of the client.

## 2. Core Technology

The client is built in Python and leverages the `libtorrent` library. `libtorrent` is a feature-complete and highly optimized C++ library for BitTorrent, with official Python bindings. It is the engine behind many popular BitTorrent clients (e.g., qBittorrent, Deluge) and is known for its high performance and low memory usage, making it the ideal choice for meeting our speed and performance goals.

## 3. Architecture

The client is designed with a modular architecture, separating concerns into distinct components:

*   **`client.py` (Core Client):** This module will contain the `MeerkoClient` class, which encapsulates all the `libtorrent` session management. It will be responsible for:
    *   Initializing and managing the BitTorrent session.
    *   Adding torrents from files or magnet links.
    *   Monitoring download progress, speed, and peer connections.
    *   Applying configuration settings, such as proxy settings.

*   **`config.py` (Configuration):** This module will handle loading and managing user settings. Initially, it will focus on proxy configuration to enable anonymous downloading. Settings might be loaded from a simple configuration file (e.g., `config.ini` or `config.json`). The key settings will be:
    *   Proxy type (e.g., SOCKS5)
    *   Proxy host and port
    *   Proxy username and password (optional)
    *   A flag to enable/disable peer-level anonymity features within `libtorrent`.

*   **`cli.py` (Command-Line Interface):** This module will provide the user interface for interacting with the client. It will use Python's `argparse` library to parse command-line arguments. The CLI will allow users to:
    *   Start a new download using a `.torrent` file.
    *   Specify a save location for the downloaded files.
    *   View real-time progress of the download (e.g., percentage complete, download speed, number of peers).

## 4. Security and Anonymity

The primary security goal is to make the user's IP address less visible to peers in the swarm. This will be achieved by implementing robust proxy support.

When a proxy is configured and enabled, `libtorrent` will be instructed to route all of its communication—including tracker announcements and peer-to-peer connections—through the specified proxy server. This prevents the client from making direct connections to other peers, effectively masking the user's real IP address with the IP address of the proxy.

The client will be configured to use `libtorrent`'s specific flags for enhanced privacy, such as disabling peer exchange (PEX) with peers that are not from the tracker, to avoid leaking the user's IP address through other channels.

## 5. Workflow

1.  The user launches the client via the command line, providing a path to a `.torrent` file.
2.  The `cli.py` module parses the arguments.
3.  The application loads settings from the configuration file using `config.py`.
4.  An instance of the `MeerkoClient` from `client.py` is created.
5.  The client initializes a `libtorrent` session with the specified settings (including proxy settings).
6.  The `.torrent` file is added to the session.
7.  The client enters a loop where it periodically prints the download status (progress, speed, peers) to the console.
8.  The loop continues until the download is complete or the user terminates the client.
9.  Once the download is finished, the client will shut down the `libtorrent` session gracefully.
