#!/usr/bin/env bash
# Convenience launcher: creates a venv on first run, then starts Jarvis.
# Usage: ./run.sh            (text mode)
#        ./run.sh --voice    (voice mode)
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "First run: creating virtual environment…"
  python3 -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt
fi

exec ./.venv/bin/python main.py "$@"
