# Meerko Bittorent

Uses the `web-app-stack` skill, adapted. Shape: single-user desktop app (Python + libtorrent + tkinter);
no hosting, no database, no Electron/Tauri shell. Delivered as GitHub Releases from `v*` tags.

## Rules for this repo

- Every `.py` file starts with `# SPDX-License-Identifier: GPL-3.0-or-later` (enforced by `tests/test_license_headers.py`).
- LF line endings everywhere (`.gitattributes`); `*.bat`/`*.ps1` are the only CRLF files.
- `__version__` in `meerko_bittorent/__init__.py` is the single version source. CI rewrites it with
  `packaging/stamp_version.py`; edit it by hand only for dev bumps. Keep the version regex in
  `stamp_version.py` and `build-appimage.sh` identical.
- libtorrent APIs: stay within what 2.0.5 through 2.0.12 all provide (Ubuntu 22.04 builds the AppImage with 2.0.5).
- Tests never create a Tk root window (no display in CI or the Nix build sandbox).
- Never add `__init__.py` to `packaging/`: it would shadow the PyPI `packaging` library.
- Every release is signed with GPG key `A831ABC3E4CA419F45A5F0CAAE8BE4A90597C13C`; never switch keys or mix
  signed and unsigned releases within a major version.
- Never commit secrets (`config.ini`, private keys).
- Work on `master`; design docs live in the git-ignored `docs/` folder.

## Commands

- Dev shell: `nix develop` (or the Ubuntu venv described in README)
- Tests: `nix flake check` / `python -m pytest`
- Run: `nix run .` / `python -m meerko_bittorent`
- Local AppImage: `pyinstaller --noconfirm packaging/meerko-bittorent.spec && packaging/build-appimage.sh <version>`
  (on the NixOS host, not inside distrobox: the host's AppImage binfmt handler is not visible in the container)
- Release: push tag `vX.Y.Z`; dry run via Actions → release → Run workflow
