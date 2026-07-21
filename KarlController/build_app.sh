#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
APP="$BUILD_DIR/Karl Controller.app"
CONTENTS="$APP/Contents"
ICONSET="$BUILD_DIR/AppIcon.iconset"
ICON_BASE="$BUILD_DIR/AppIcon-1024.png"

swift build --package-path "$SCRIPT_DIR" -c release

mkdir -p "$CONTENTS/MacOS" "$CONTENTS/Resources"
cp "$SCRIPT_DIR/.build/release/KarlController" "$CONTENTS/MacOS/KarlController"
cp "$SCRIPT_DIR/Info.plist" "$CONTENTS/Info.plist"
chmod +x "$CONTENTS/MacOS/KarlController"

swift "$SCRIPT_DIR/generate_icon.swift" "$ICON_BASE"
rm -rf "$ICONSET"
mkdir -p "$ICONSET"
sips -z 16 16 "$ICON_BASE" --out "$ICONSET/icon_16x16.png" >/dev/null
sips -z 32 32 "$ICON_BASE" --out "$ICONSET/icon_16x16@2x.png" >/dev/null
sips -z 32 32 "$ICON_BASE" --out "$ICONSET/icon_32x32.png" >/dev/null
sips -z 64 64 "$ICON_BASE" --out "$ICONSET/icon_32x32@2x.png" >/dev/null
sips -z 128 128 "$ICON_BASE" --out "$ICONSET/icon_128x128.png" >/dev/null
sips -z 256 256 "$ICON_BASE" --out "$ICONSET/icon_128x128@2x.png" >/dev/null
sips -z 256 256 "$ICON_BASE" --out "$ICONSET/icon_256x256.png" >/dev/null
sips -z 512 512 "$ICON_BASE" --out "$ICONSET/icon_256x256@2x.png" >/dev/null
sips -z 512 512 "$ICON_BASE" --out "$ICONSET/icon_512x512.png" >/dev/null
cp "$ICON_BASE" "$ICONSET/icon_512x512@2x.png"
iconutil -c icns "$ICONSET" -o "$CONTENTS/Resources/AppIcon.icns"

codesign --force --deep --sign - "$APP"

if [[ "${1:-}" == "--install" ]]; then
    INSTALLED_APP="$HOME/Desktop/Karl Controller.app"
    ditto "$APP" "$INSTALLED_APP"
    echo "Installed: $INSTALLED_APP"
else
    echo "Built: $APP"
fi
