#!/bin/bash
set -e
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"
if ! command -v python3 >/dev/null 2>&1; then
  osascript -e 'display dialog "Python 3 is required. Please install Python 3, then run this launcher again." buttons {"OK"} with icon stop'
  exit 1
fi
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
if ! python -c "import streamlit, pandas, openpyxl" >/dev/null 2>&1; then
  python -m pip install -r requirements.txt
fi
python run_app.py
