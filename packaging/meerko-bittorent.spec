# SPDX-License-Identifier: GPL-3.0-or-later
# -*- mode: python ; coding: utf-8 -*-
# PyInstaller build spec, run from the repo root: pyinstaller --noconfirm packaging/meerko-bittorent.spec
#   Windows -> dist/meerko-bittorent.exe (windowed) + dist/meerko-bittorent-cli.exe (console), both onefile
#   Linux   -> dist/meerko-bittorent/ holding both executables (onedir, packed into an AppImage by build-appimage.sh)
import os
import sys

# SPECPATH is injected by PyInstaller: the directory containing this spec (packaging/)
repository_root = os.path.dirname(SPECPATH)
package_directory = os.path.join(repository_root, "meerko_bittorent")
icon_path = os.path.join(repository_root, "assets", "Meerko Bittorent.ico")
is_windows = sys.platform == "win32"

# (executable name, entry script, needs a console window)
PROGRAMS = (
    ("meerko-bittorent", os.path.join(package_directory, "__main__.py"), False),
    ("meerko-bittorent-cli", os.path.join(package_directory, "cli.py"), True),
)


# Dependency analysis for one entry script
def analyse(entry_script):
    return Analysis(
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


# Windows: one self-contained executable per program, with the application icon
def build_windows_program(name, analysis, console):
    return EXE(
        PYZ(analysis.pure),
        analysis.scripts,
        analysis.binaries,
        analysis.datas,
        [],
        name=name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        runtime_tmpdir=None,
        console=console,
        icon=[icon_path],
    )


# Linux: an executable whose libraries are collected into the shared onedir below
def build_linux_program(name, analysis, console):
    return EXE(
        PYZ(analysis.pure),
        analysis.scripts,
        [],
        exclude_binaries=True,
        name=name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=console,
    )


build_program = build_windows_program if is_windows else build_linux_program
collect_inputs = []
# Build every program; on Linux also gather its libraries for the one shared folder
for program_name, program_script, program_console in PROGRAMS:
    program_analysis = analyse(program_script)
    program_executable = build_program(program_name, program_analysis, program_console)
    collect_inputs.extend([program_executable, program_analysis.binaries, program_analysis.datas])

# Linux: both executables share one directory, so duplicated libraries are stored once
if not is_windows:
    collection = COLLECT(*collect_inputs, strip=False, upx=False, name="meerko-bittorent")
