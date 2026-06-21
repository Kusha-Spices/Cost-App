#!/usr/bin/env bash
# Double-click this in Finder to launch the Jarvis menu-bar app.
# First run installs everything automatically.
cd "$(dirname "$0")"
[ -d .venv ] || ./install.sh
exec ./.venv/bin/python menubar.py
