#!/usr/bin/env bash
# Double-click this in Finder to launch the Jarvis menu-bar app (no build needed).
# First run sets up the virtual environment and installs dependencies.
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  /usr/bin/env python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip
  ./.venv/bin/pip install -r requirements.txt
fi
exec ./.venv/bin/python menubar.py
