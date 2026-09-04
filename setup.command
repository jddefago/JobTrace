#!/bin/bash
# One-time setup for a fresh JobTrace download on macOS. Safe to re-run any
# time — it only ever (re)creates the launcher and starts the server.
#
# Double-click this file in Finder, or run ./setup.command from Terminal.
set -u
cd "$(dirname "$0")"
PROJ="$(pwd)"

echo "JobTrace setup"
echo "=============="
echo

# 1. A downloaded zip / AirDrop / cloud copy is quarantined by macOS and the
#    scripts lose their exec bit. Clear both so nothing nags on launch.
if command -v xattr >/dev/null 2>&1; then
    xattr -dr com.apple.quarantine . >/dev/null 2>&1 || true
fi
chmod +x start.command stop.command setup.command 2>/dev/null || true

# 2. Python check — the app needs nothing but the standard library.
PYEXE=""
if command -v python3 >/dev/null 2>&1; then PYEXE="python3"
elif command -v python >/dev/null 2>&1; then PYEXE="python"; fi
if [ -z "$PYEXE" ]; then
    echo "  Python 3 was not found."
    echo "  Install it from https://www.python.org/downloads/ and run this again."
    echo
    read -r -p "Press Enter to close..." _
    exit 1
fi
echo "  Python: $($PYEXE --version 2>&1)"

# 3. Build a double-clickable JobTrace.app on the Desktop. Regenerated every
#    run (so it can never point at a stale path), unquarantined, with the
#    project location baked in. Move the project later -> re-run this.
APP="$HOME/Desktop/JobTrace.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>JobTrace</string>
  <key>CFBundleDisplayName</key><string>JobTrace</string>
  <key>CFBundleIdentifier</key><string>com.jobtrace.launcher</string>
  <key>CFBundleExecutable</key><string>JobTrace</string>
  <key>CFBundleIconFile</key><string>JobTrace</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSUIElement</key><true/>
  <key>LSMinimumSystemVersion</key><string>10.13</string>
</dict></plist>
PLIST
cat > "$APP/Contents/MacOS/JobTrace" <<LAUNCH
#!/bin/bash
exec /bin/bash "$PROJ/start.command"
LAUNCH
chmod +x "$APP/Contents/MacOS/JobTrace"

# Optional icon: convert the app logo to .icns with stock macOS tools.
if command -v sips >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1 \
   && [ -f frontend/assets/logo.png ]; then
    _ico="$(mktemp -d)/JobTrace.iconset"
    mkdir -p "$_ico"
    for sz in 16 32 64 128 256 512; do
        sips -z $sz $sz frontend/assets/logo.png --out "$_ico/icon_${sz}x${sz}.png" >/dev/null 2>&1
        d=$((sz*2))
        sips -z $d $d frontend/assets/logo.png --out "$_ico/icon_${sz}x${sz}@2x.png" >/dev/null 2>&1
    done
    iconutil -c icns "$_ico" -o "$APP/Contents/Resources/JobTrace.icns" >/dev/null 2>&1 || true
    rm -rf "$(dirname "$_ico")"
fi
echo "  Created ~/Desktop/JobTrace.app  —  drag it to your Dock for one-click launch"

# 4. Start the server and open the dashboard.
echo
./start.command

cat <<EOF

  JobTrace is running at http://localhost:8766

  Gmail sync is OPTIONAL and off by default. The tracker works fully
  without it. To turn it on later, open the dashboard, click the Gmail
  pill (top-right) and choose "Sync settings" — or ask your AI assistant
  to "set up JobTrace Gmail sync" and point it at SETUP.md.

EOF
read -r -p "Press Enter to close..." _
