# Third-Party Notices

Meerko Bittorent is licensed under the GNU General Public License v3.0 or later (see `LICENSE`).

The release binaries (Windows `.exe` and Linux `.AppImage`) bundle the following third-party components.
They are redistributed under their own licenses, all of which are compatible with GPL-3.0-or-later.

| Component | License | Upstream |
|---|---|---|
| libtorrent (rasterbar) and its Python bindings | BSD-3-Clause | https://github.com/arvidn/libtorrent |
| CPython runtime and standard library | PSF-2.0 | https://www.python.org/ |
| Tcl/Tk (via tkinter) | TCL license (BSD-style) | https://www.tcl-lang.org/ |
| Boost (linked into libtorrent) | BSL-1.0 | https://www.boost.org/ |
| OpenSSL 3.x (used by libtorrent, Linux AppImage) | Apache-2.0 | https://www.openssl.org/ |
| OpenSSL 1.1.1 (used by libtorrent, Windows executable; DLLs from the Python 3.10 runtime) | OpenSSL / SSLeay dual license | https://www.openssl.org/ |
| PyInstaller bootloader | GPL-2.0-or-later with bootloader exception | https://pyinstaller.org/ |

The Nix package does not bundle these components; Nix supplies them from nixpkgs under their own licenses.
