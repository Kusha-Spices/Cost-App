"""Speech: text-to-speech via macOS `say`, speech-to-text via SpeechRecognition."""
from __future__ import annotations

import re
import subprocess


def _clean_for_speech(text: str) -> str:
    text = re.sub(r"```.*?```", " (code) ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"[*_#>`]+", "", text)
    return text.strip()


class Voice:
    def __init__(self, voice_name: str = "Samantha", listen: bool = True, tts_cmd: str = ""):
        self.voice_name = voice_name
        self.tts_cmd = tts_cmd          # optional external TTS (e.g. a cloned voice)
        self._recognizer = None
        self._mic = None
        if listen:
            self._setup_mic()

    @property
    def can_listen(self) -> bool:
        return self._mic is not None

    def _setup_mic(self) -> None:
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._mic = sr.Microphone()
        except Exception as e:
            print(f"[voice] Microphone unavailable ({e}).\n"
                  "        Install with: brew install portaudio && pip install pyaudio")

    def speak(self, text: str) -> None:
        text = _clean_for_speech(text)
        if not text:
            return
        # Custom voice engine (e.g. a cloned voice) — receives text on stdin.
        if self.tts_cmd:
            try:
                subprocess.run(self.tts_cmd, shell=True, input=text, text=True)
                return
            except Exception:
                pass  # fall back to the built-in voice
        try:
            r = subprocess.run(["say", "-v", self.voice_name, text])
            if r.returncode != 0:
                subprocess.run(["say", text])
        except Exception:
            pass

    def listen(self) -> str:
        """Record one utterance from the mic and transcribe it."""
        if not self.can_listen:
            return ""
        import speech_recognition as sr
        with self._mic as source:
            self._recognizer.adjust_for_ambient_noise(source, duration=0.4)
            try:
                audio = self._recognizer.listen(source, timeout=8, phrase_time_limit=20)
            except sr.WaitTimeoutError:
                return ""
        try:
            return self._recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            print(f"[voice] Speech recognition error: {e}")
            return ""
