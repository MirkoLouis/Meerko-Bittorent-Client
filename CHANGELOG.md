# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
