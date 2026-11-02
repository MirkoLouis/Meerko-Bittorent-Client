#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Pack the PyInstaller onedir build (dist/meerko-bittorent/) into an AppImage.
# Usage (from the repo root, after `pyinstaller packaging/meerko-bittorent.spec`):
#   packaging/build-appimage.sh <version>
# Output: dist/Meerko-Bittorent-<version>-x86_64.AppImage
set -euo pipefail

# Same accepted versions as packaging/stamp_version.py (keep the two patterns identical)
readonly VERSION_PATTERN='^[0-9]+\.[0-9]+\.[0-9]+((a|b|rc)[0-9]+)?(\.dev[0-9]+)?$'
readonly APPIMAGETOOL_URL='https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage'

# Validate the single version argument before using it in any path
if [ "$#" -ne 1 ] || [[ ! "$1" =~ $VERSION_PATTERN ]]; then
    echo "usage: $0 <version>  (e.g. 1.2.3, 1.2.3rc1, 1.2.3.dev0)" >&2
    exit 2
fi
readonly version="$1"

# Resolve all paths from the repository root so the script works from any directory
repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly repository_root
readonly onedir_build="$repository_root/dist/meerko-bittorent"
readonly appimage_files="$repository_root/packaging/appimage"
readonly app_dir="$repository_root/AppDir"
readonly output_path="$repository_root/dist/Meerko-Bittorent-$version-x86_64.AppImage"

# The PyInstaller step must have run first
if [ ! -x "$onedir_build/meerko-bittorent" ]; then
    echo "missing $onedir_build/meerko-bittorent; run pyinstaller packaging/meerko-bittorent.spec first" >&2
    exit 1
fi

# Assemble a fresh AppDir: bundled app, entry point, desktop file and icons
rm -rf -- "$app_dir"
mkdir -p -- "$app_dir/usr/lib"
cp -a -- "$onedir_build" "$app_dir/usr/lib/meerko-bittorent"
install -m 755 -- "$appimage_files/AppRun" "$app_dir/AppRun"
cp -- "$appimage_files/meerko-bittorent.desktop" "$app_dir/"
cp -- "$appimage_files/meerko-bittorent.png" "$app_dir/"
cp -- "$appimage_files/meerko-bittorent.png" "$app_dir/.DirIcon"

# Download appimagetool into a temporary directory that is always cleaned up
tool_dir="$(mktemp -d)"
readonly tool_dir
trap 'rm -rf -- "$tool_dir"' EXIT
curl --fail --location --silent --show-error --output "$tool_dir/appimagetool" -- "$APPIMAGETOOL_URL"
chmod +x -- "$tool_dir/appimagetool"

# Build; extract-and-run avoids needing FUSE on CI runners and in containers
APPIMAGE_EXTRACT_AND_RUN=1 ARCH=x86_64 "$tool_dir/appimagetool" --no-appstream "$app_dir" "$output_path"
echo "built $output_path"
