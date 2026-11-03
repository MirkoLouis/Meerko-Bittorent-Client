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
| `Meerko-Bittorent-<version>-windows-x86_64.exe` | Windows 10/11, 64-bit: the desktop app |
| `Meerko-Bittorent-<version>-windows-x86_64-cli.exe` | Windows 10/11, 64-bit: the command-line client (optional) |
| `Meerko-Bittorent-<version>-x86_64.AppImage` | Linux, 64-bit (glibc 2.35 or newer): app and command line in one file |
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
sudo apt install python3-libtorrent python3-tk python3-jeepney python3-venv
python3 -m venv --system-site-packages .venv-linux
source .venv-linux/bin/activate        # fish: source .venv-linux/bin/activate.fish
python -m meerko_bittorent
```

`--system-site-packages` lets the virtual environment use the libtorrent bindings installed by apt.

### Windows

Requires Python 3.13.

```bash
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m meerko_bittorent
```

## Usage

Meerko comes as two commands built on the same engine:

| Command | What it is |
|---|---|
| `meerko-bittorent` | The desktop app (`python -m meerko_bittorent` from source) |
| `meerko-bittorent-cli` | The command-line client (`python -m meerko_bittorent.cli` from source) |

On Windows these are two separate `.exe` downloads. The AppImage contains both: run it normally for the app,
or as `./Meerko-Bittorent-<version>-x86_64.AppImage cli …` for the command line. Most people should use the
desktop app from a prebuilt release (see [Download](#download)).

### Command line

```bash
meerko-bittorent-cli "path/to/your.torrent" "path/to/save/directory"
meerko-bittorent-cli "magnet:?xt=urn:btih:..." "path/to/save/directory"
meerko-bittorent-cli --proxy-type socks5 --proxy-host 127.0.0.1 --proxy-port 1080 "magnet:?..." "downloads"
```

The client downloads, seeds until a 1.0 share ratio, then exits. `Ctrl+C` stops it cleanly. See
[COMMANDS.md](COMMANDS.md) for every option, where the proxy password comes from, and the exit codes.

### Running the CLI and the app together

Each command runs its own engine, so you can download **different** torrents in the app and on the command line
at the same time (they share your bandwidth). The **same** torrent is refused in a second window or terminal with
"already being downloaded by another Meerko process", because two programs writing the same files would corrupt
them.

Meerko handles one torrent per window on purpose: its author downloads one torrent at a time, so a multi-torrent
list is not planned. Open a second window or terminal if you need two at once.

### Settings file

Both commands read the same `config.ini`:

*   Linux: `~/.config/meerko-bittorent/config.ini` (or `$XDG_CONFIG_HOME/meerko-bittorent/config.ini`)
*   Windows: `%APPDATA%\meerko-bittorent\config.ini`

The app's **Save as default** button writes it for you; [`config.ini.example`](config.ini.example) shows the
format. The app never saves your proxy password. If you add one to the file yourself, make the file private
(`chmod 600` on Linux); both commands warn you if other users can read it.

### File pickers on Linux

The **Browse** buttons open your desktop's own file chooser (GNOME, KDE, GTK) through the XDG Desktop Portal. If no
portal is available, Meerko falls back to a simpler built-in dialog. On tiling compositors such as Hyprland or Sway
the portal only starts inside a systemd graphical session; on NixOS that is `programs.hyprland.withUWSM = true;`
(then log in with the "uwsm-managed" Hyprland session). On Windows the normal Explorer dialog is used.

### Choosing a proxy

A proxy hides your IP address from peers, **not** from whoever runs the proxy: they see your real IP and every
torrent you join. Use a SOCKS5 proxy you trust, ideally one that supports UDP (BitTorrent's DHT and uTP need it),
such as one offered by a paid VPN provider or a server you control. Avoid free public proxy lists: their operators
are unknown and may log or tamper with traffic, most do not support UDP, they stop working within minutes, and
many relay through machines whose owners never agreed to it.

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
