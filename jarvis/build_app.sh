#!/usr/bin/env bash
# Build Jarvis.app (a background menu-bar app) with py2app. Run this ON YOUR MAC.
set -e
cd "$(dirname "$0")"

[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -U -r requirements.txt py2app

# Build the .icns app icon from assets/icon.png (macOS `sips`).
# Generate the default only if you haven't dropped in your own icon.png.
[ -f assets/icon.png ] || python assets/make_icon.py
if command -v sips >/dev/null 2>&1 && [ -f assets/icon.png ]; then
  sips -s format icns assets/icon.png --out assets/icon.icns >/dev/null 2>&1 || true
fi

rm -rf build dist
python setup.py py2app

echo
echo "✅ Built dist/Jarvis.app"
echo "   • Drag it to /Applications (or run: open dist/Jarvis.app)"
echo "   • First launch: grant Microphone, Screen Recording, and Accessibility"
echo "     to *Jarvis* in System Settings → Privacy & Security."
echo "   • Put your key in a .env next to the app, or export ANTHROPIC_API_KEY."
