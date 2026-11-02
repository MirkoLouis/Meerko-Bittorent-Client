# Meerko Bittorent Client

A secure, fast, and anonymous BitTorrent client built with Python.

<img width="472" height="532" alt="Screenshot 2025-11-25 185821" src="https://github.com/user-attachments/assets/27c725f6-763f-4f55-ae7c-97b396c6504e" />

## Features

*   **Secure & Anonymous:** Prioritizes user privacy by routing traffic through a proxy, hiding your IP from peers.
*   **High Performance:** Built using the powerful and efficient `libtorrent` library.
*   **Easy to Use:** A simple desktop interface, built on top of a command-line client.
*   **Automatic Seeding Stop:** Automatically stops seeding when a share ratio of 1.0 is reached, ensuring you contribute fairly to the swarm.

## Download

Prebuilt binaries are attached to each [GitHub Release](https://github.com/MirkoLouis/Meerko-Bittorent-Client/releases).

| File | Platform |
|---|---|
| `Meerko-Bittorent-<version>-windows-x86_64.exe` | Windows 10/11, 64-bit |
| `Meerko-Bittorent-<version>-x86_64.AppImage` | Linux, 64-bit (glibc 2.35 or newer) |
| `SHA256SUMS`, `SHA256SUMS.asc` | Checksums and their GPG signature |

### Verify your download

Releases are signed with this key (also in [`packaging/release-signing-key.asc`](packaging/release-signing-key.asc)):

```
A831 ABC3 E4CA 419F 45A5  F0CA AE8B E4A9 0597 C13C
```

```bash
gpg --import release-signing-key.asc
gpg --verify SHA256SUMS.asc SHA256SUMS
sha256sum -c --ignore-missing SHA256SUMS
```

### Platform notes

*   **Windows:** the executable is not code-signed yet, so SmartScreen shows "Windows protected your PC".
    Choose **More info → Run anyway** after verifying the checksum.
*   **Linux AppImage:** `chmod +x Meerko-Bittorent-*.AppImage` and run it. If your system lacks FUSE, run it with
    `--appimage-extract-and-run`.

## Nix

Run directly from the repository:

```bash
nix run github:MirkoLouis/Meerko-Bittorent-Client
```

Development shell (Python with libtorrent, tkinter and pytest, no virtual environment needed):

```bash
nix develop
python -m meerko_bittorent
```

## Running from source

### Ubuntu / Debian

```bash
sudo apt install python3-libtorrent python3-tk python3-venv
python3 -m venv --system-site-packages .venv-linux
source .venv-linux/bin/activate        # fish: source .venv-linux/bin/activate.fish
python -m meerko_bittorent
```

`--system-site-packages` lets the virtual environment use the libtorrent bindings installed by apt.

### Windows

Requires Python 3.10.

```bash
py -3.10 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m meerko_bittorent
```

## Usage

> **Note:** the command-line interface is being reworked so the desktop app runs on top of it.
> `python -m meerko_bittorent` currently opens the desktop app; the commands below describe the CLI.

To download a torrent, you can run the client from the command line, providing a path to a `.torrent` file or a magnet link, or use a prebuilt release (see [Download](#download)), the recommended way for most people.

```bash
python -m meerko_bittorent <torrent_source> <save_path>
```

For a detailed reference of all commands and options, please see the [COMMANDS.md](COMMANDS.md) file.

### Examples

**Downloading from a `.torrent` file:**
```bash
python -m meerko_bittorent "path/to/your.torrent" "path/to/save/directory"
```

**Downloading from a magnet link:**
```bash
python -m meerko_bittorent "magnet:?xt=urn:btih:..." "path/to/save/directory"
```

### Using a Proxy

The client can be configured to use a proxy for anonymity. You can do this in two ways:

#### 1. Default Proxy with `config.ini`

For a more permanent setup, you can use the `config.ini` file:

1.  Rename `config.ini.example` to `config.ini`.
2.  Edit `config.ini` with your proxy details.

The client will automatically use these settings every time it runs.

#### 2. Command-Line Arguments

You can specify a proxy for a single run using command-line arguments. These will override the settings in `config.ini`.

```bash
python -m meerko_bittorent "magnet:?xt=urn:btih:..." "path/to/save/directory" --proxy-type socks5 --proxy-host your-proxy-host --proxy-port your-proxy-port
```

To disable the proxy for a single run, use the `--no-proxy` flag.

## Development

```bash
nix flake check          # builds the package and runs the tests
python -m pytest         # inside nix develop or the Ubuntu venv
```

Releases are built by GitHub Actions: pushing a tag `vX.Y.Z` builds the Windows executable and the AppImage,
signs the checksums and publishes the release.

## License

Meerko Bittorent is free software, licensed under the [GNU General Public License v3.0 or later](LICENSE).
Release binaries bundle third-party components under their own licenses; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
