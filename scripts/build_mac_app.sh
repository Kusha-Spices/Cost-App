#!/bin/bash
#
# Build "Kusha Costing App.app" on a Mac.
#
# Produces a self-contained app that bundles Python, Streamlit and every
# dependency, so the people who use it need nothing installed.
#
# Usage (in Terminal, from anywhere):
#     bash scripts/build_mac_app.sh
#
# The finished app is left at:  dist/Kusha Costing App.app
#
set -euo pipefail

cd "$(dirname "$0")/.."
PROJECT_DIR="$(pwd)"
echo "Project: $PROJECT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required to build. Install it from https://www.python.org/downloads/ and retry."
  exit 1
fi

echo "==> Creating an isolated build environment"
python3 -m venv .build-venv
# shellcheck disable=SC1091
source .build-venv/bin/activate

echo "==> Installing dependencies"
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt pyinstaller

echo "==> Building the app (this can take a few minutes)"
pyinstaller --noconfirm --clean KushaCostingApp.spec

echo ""
echo "Done."
echo "App built at: $PROJECT_DIR/dist/Kusha Costing App.app"
echo ""
echo "Next steps:"
echo "  1. Drag 'Kusha Costing App.app' into your Applications folder."
echo "  2. The first time, right-click it -> Open (because it is not code-signed),"
echo "     then click Open in the dialog. After that you can open it normally."
echo "  3. It launches the app in your web browser automatically."
