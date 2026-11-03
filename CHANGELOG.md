# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

*   Nix flake: `nix run`, `nix develop` dev shell and `nix flake check` (builds the package and runs the tests).
*   `pyproject.toml` packaging with a `meerko-bittorent` entry point.
*   Linux AppImage build and a cross-platform PyInstaller spec.
*   GitHub Actions: CI on every push and pull request; tag-driven releases with the Windows executable,
    the AppImage, and GPG-signed `SHA256SUMS`.
*   Smoke tests, license-header test and a validated version-stamping script.
*   GPL-3.0-or-later license and third-party notices for bundled components.
*   `meerko-bittorent-cli`: a working command-line client (download, seed to 1.0, clean `Ctrl+C`, exit codes).
*   Shared engine used by both the desktop app and the CLI; they can download different torrents at the same time.
*   Cross-process lock: the same torrent cannot run in two Meerko processes at once.
*   Per-user `config.ini` (`~/.config/meerko-bittorent/` or `%APPDATA%\meerko-bittorent\`), read by both commands.
*   Desktop app: proxy fields pre-filled from `config.ini`, and a **Save as default** button (never saves the password).
*   Proxy password from `config.ini`, `MEERKO_PROXY_PASSWORD`, or a hidden prompt; warning when a stored password is readable by others.
*   Windows releases include a separate console `…-cli.exe`; the AppImage runs the CLI with `cli` as first argument.
*   Release builds smoke-test the frozen CLI (`--version`) on Windows and Linux.
*   Linux: the Browse buttons open the desktop's native file chooser via the XDG Desktop Portal (built-in dialog as fallback).
*   Privacy modes: with a proxy Meerko fails closed (no router port opening, no LAN discovery, no direct incoming
    connections, identity hidden from trackers); HTTP proxies run in a reduced mode without DHT, uTP and UDP trackers.
*   The app shows the active privacy mode; the CLI logs it, plus notes such as "No HTTP trackers".
*   Offline leak tests prove that nothing is contacted directly with a proxy, on libtorrent 2.0.12 and 2.0.5.

### Changed

*   Desktop app: proxy type is a dropdown; invalid input, torrent/disk errors and lock conflicts are shown instead of
    "finished"; closing the window stops a running download cleanly.
*   Proxy logins now work: a username selects libtorrent's authenticated SOCKS5/HTTP proxy types.
*   Proxy form errors name the actual problem (empty host, empty port, non-numeric or out-of-range port, missing password).
*   With a proxy the log says "Not accepting incoming connections (proxy mode)" instead of "listening on port 0".
*   Protocol encryption is preferred (encrypted first, plain still accepted).
*   Seeding stops at a 1.0 ratio of payload uploaded; protocol overhead no longer counts.
*   Line endings are normalized to LF via `.gitattributes`.
*   The version now lives in `meerko_bittorent/__init__.py` (`__version__`) and is stamped from the git tag at release.
*   Windows builds use Python 3.13 and `libtorrent` 2.0.15, whose wheel has OpenSSL 3 built in. The previous
    build needed OpenSSL 1.1 DLLs it did not ship (end-of-life, GPL-incompatible) and failed to start on clean machines.

### Removed

*   `--proxy-pass` (passwords on the command line leak into shell history and the process list).
*   Reading `config.ini` from the current working directory; use the per-user location or `--config PATH`.
*   `client.py`, replaced by `engine.py`.
*   Deprecated libtorrent settings: `force_proxy`, `cache_size`, `active_downloads` and `active_seeds`.

## [0.7.0] - 2025-11-25

### Changed

*   The project now requires Python 3.10 and a virtual environment.

## [0.6.0] - 2025-11-25

### Added

*   Automatic seeding stop when a share ratio of 1.0 is reached.
*   The share ratio is now displayed in the status line while seeding.

### Changed

*   The main download loop in `client.py` now continues until the share ratio is met, instead of stopping immediately after the download is complete.
*   Updated `README.md` to include automatic seeding stop in the features list.

## [0.5.0] - 2025-11-25

### Added

*   Graceful stop functionality for downloads using `Ctrl+C`. The client will now remove the torrent from the session and shut down cleanly upon interruption.

### Changed

*   Updated `COMMANDS.md` to include information about stopping downloads gracefully.

## [0.4.0] - 2025-11-25

### Added

*   Support for downloading from magnet links.
*   `COMMANDS.md` file with a detailed reference for all command-line arguments.

### Changed

*   The client now accepts a `torrent_source` argument, which can be a `.torrent` file path or a magnet link.
*   Updated `README.md` to reflect magnet link support and link to the new `COMMANDS.md` file.

## [0.3.0] - 2025-11-25

### Added

*   Default proxy support via a `config.ini` file.
*   `config.ini.example` to show the user how to configure the default proxy.
*   `load_proxy_settings` function in `config.py` to load settings from `config.ini`.
*   `--no-proxy` flag to the CLI to disable the default proxy.

### Changed

*   The CLI now loads proxy settings from `config.ini` by default, and command-line arguments override them.
*   Updated `README.md` with instructions on how to use the `config.ini` file.

## [0.2.0] - 2025-11-25

### Changed

*   Switched core library from `aiotorrent` to `libtorrent` to enable proxy support.
*   The project now requires Python 3.11 and a virtual environment.

### Added

*   `MeerkoClient` class in `client.py` with download and progress monitoring logic using `libtorrent`.
*   Proxy configuration support in the `MeerkoClient` for anonymous downloading.
*   Command-line interface (`cli.py`) to run the client and configure downloads.
*   Updated `README.md` with installation and usage instructions.
*   Updated `PROJECT_OVERVIEW.md` to reflect the change to `libtorrent`.

## [0.1.0] - 2025-11-25

### Added

*   Initial project structure for the Meerko Bittorent Client.
*   Created directories: `meerko_bittorent`, `tests`.
*   Created initial files: `__init__.py`, `__main__.py`, `client.py`, `config.py`, `cli.py`, `.gitignore`, `requirements.txt`, `README.md`, `PROJECT_OVERVIEW.md`, `CHANGELOG.md`.
