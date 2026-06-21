"""Speak in YOUR cloned voice (optional, experimental).

Reads text on stdin and speaks it in the voice from a short reference recording
at voices/myvoice.wav, using the open-source Coqui XTTS model (runs locally).

Setup (one time, on your Mac):
    ./.venv/bin/pip install TTS
    # record 15–30s of clear speech and save it as voices/myvoice.wav
Then point Jarvis at this script by adding to .env:
    JARVIS_TTS_CMD=./.venv/bin/python speak_clone.py

Note: this is heavy and slower than the built-in voices (it loads a neural model
each call). For everyday use, a premium built-in voice (JARVIS_VOICE) is snappier.
If anything is missing, it falls back to the macOS voice so Jarvis still talks.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "voices", "myvoice.wav")


def main() -> None:
    text = sys.stdin.read().strip()
    if not text:
        return
    if not os.path.exists(REF):
        subprocess.run(["say", text])  # no sample yet → built-in voice
        return
    try:
        from TTS.api import TTS
    except Exception:
        subprocess.run(["say", text])  # TTS not installed → built-in voice
        return
    try:
        out = os.path.join(tempfile.gettempdir(), "jarvis_voice.wav")
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
        tts.tts_to_file(text=text, speaker_wav=REF, language="en", file_path=out)
        subprocess.run(["afplay", out])
    except Exception as e:
        print(f"[clone] falling back to system voice: {e}", file=sys.stderr)
        subprocess.run(["say", text])


if __name__ == "__main__":
    main()
