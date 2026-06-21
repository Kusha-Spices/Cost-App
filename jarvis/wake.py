"""Always-listening wake-word loop: say "Jarvis ..." to give a command.

Default backend is continuous speech recognition (no extra key needed). For
lower CPU / higher accuracy you can swap in Picovoice Porcupine, which ships a
built-in "Jarvis" keyword — see the README.
"""
from __future__ import annotations


class WakeListener:
    def __init__(self, wake_words=("jarvis",), on_command=None, speak=None,
                 phrase_limit: int = 15):
        self.wake_words = [w.lower() for w in wake_words]
        self.on_command = on_command or (lambda t: None)
        self.speak = speak or (lambda t: None)
        self.phrase_limit = phrase_limit
        self._recognizer = None
        self._mic = None
        self._sr = None

    def _ensure(self) -> None:
        import speech_recognition as sr
        self._sr = sr
        self._recognizer = sr.Recognizer()
        self._mic = sr.Microphone()

    def _transcribe(self, source, timeout=None) -> str:
        sr = self._sr
        try:
            audio = self._recognizer.listen(
                source, timeout=timeout, phrase_time_limit=self.phrase_limit)
        except sr.WaitTimeoutError:
            return ""
        try:
            return self._recognizer.recognize_google(audio).lower()
        except (sr.UnknownValueError, sr.RequestError):
            return ""

    def run(self, stop_event) -> None:
        """Blocking loop until stop_event is set."""
        try:
            self._ensure()
        except Exception as e:
            print(f"[wake] microphone unavailable: {e}\n"
                  "       brew install portaudio && pip install pyaudio")
            return

        with self._mic as source:
            self._recognizer.adjust_for_ambient_noise(source, duration=0.6)
            while not stop_event.is_set():
                heard = self._transcribe(source, timeout=4)
                if not heard:
                    continue
                hit = next((w for w in self.wake_words if w in heard), None)
                if not hit:
                    continue
                # Anything spoken after the wake word is the command.
                cmd = heard.split(hit, 1)[1].strip(" ,.:!?")
                if not cmd:
                    self.speak("Yes?")
                    cmd = self._transcribe(source, timeout=6)
                if cmd:
                    self.on_command(cmd)   # runs synchronously; mic idle meanwhile
