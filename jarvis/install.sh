#!/usr/bin/env bash
# One-shot installer. Run once after unzipping:  ./install.sh
set -e
cd "$(dirname "$0")"

echo "Setting up Jarvis…"
if ! command -v python3 >/dev/null 2>&1; then
  echo "✗ Python 3 not found. Install Apple's command-line tools first:"
  echo "    xcode-select --install"
  echo "  (or get Python from https://www.python.org/downloads/macos/), then re-run."
  exit 1
fi

python3 -m venv .venv
./.venv/bin/pip install --upgrade pip >/dev/null
./.venv/bin/pip install -r requirements.txt
[ -f .env ] || cp .env.example .env

echo
echo "✅ Installed. Two steps left:"
echo "   1) Put your Anthropic API key in:  $(pwd)/.env"
echo "   2) Start Jarvis:"
echo "        ./.venv/bin/python menubar.py        # menu-bar app (🤖)"
echo "        ./.venv/bin/python main.py --wake     # terminal + wake word"
echo
echo "Optional — voice INPUT (talking to it):"
echo "        brew install portaudio && ./.venv/bin/pip install pyaudio"
echo
echo "Grant your terminal (or Jarvis.app) Accessibility, Screen Recording, and"
echo "Microphone access in System Settings → Privacy & Security."
