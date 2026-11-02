# SPDX-License-Identifier: GPL-3.0-or-later
# -*- mode: python ; coding: utf-8 -*-
# PyInstaller build spec, run from the repo root: pyinstaller --noconfirm packaging/meerko-bittorent.spec
#   Windows -> dist/meerko-bittorent.exe        (onefile, windowed, with icon)
#   Linux   -> dist/meerko-bittorent/           (onedir, packed into an AppImage by build-appimage.sh)
import os
import sys

# SPECPATH is injected by PyInstaller: the directory containing this spec (packaging/)
repository_root = os.path.dirname(SPECPATH)
application_name = "meerko-bittorent"
entry_script = os.path.join(repository_root, "meerko_bittorent", "__main__.py")
icon_path = os.path.join(repository_root, "assets", "Meerko Bittorent.ico")
is_windows = sys.platform == "win32"

# Dependency analysis shared by both platforms
analysis = Analysis(
    [entry_script],
    pathex=[repository_root],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
python_archive = PYZ(analysis.pure)

# Windows: one self-contained executable with the application icon
if is_windows:
    executable = EXE(
        python_archive,
        analysis.scripts,
        analysis.binaries,
        analysis.datas,
        [],
        name=application_name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        runtime_tmpdir=None,
        console=False,
        icon=[icon_path],
    )

# Linux: a directory build, which the AppImage wraps
if not is_windows:
    executable = EXE(
        python_archive,
        analysis.scripts,
        [],
        exclude_binaries=True,
        name=application_name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
    )
    collection = COLLECT(
        executable,
        analysis.binaries,
        analysis.datas,
        strip=False,
        upx=False,
        name=application_name,
    )
