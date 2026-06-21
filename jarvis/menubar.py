"""Jarvis as a macOS menu-bar app.

Run directly:   python menubar.py
Or build a .app: ./build_app.sh   (see README)

Lives in the menu bar (🤖). Click it to type a request, toggle the wake word,
toggle auto-approve, or quit. Confirmations use a native dialog, so it works
with no terminal attached.
"""
from __future__ import annotations

import os
import subprocess
import threading

import rumps

from config import Config, JARVIS_DIR, LOG_PATH
from safety import SafetyManager

ICON = os.path.join(JARVIS_DIR, "assets", "icon.png")


def gui_confirm(prompt: str) -> bool:
    """Native confirm dialog. Runs as a subprocess, so it's thread-safe."""
    text = prompt.strip().replace("\\", "\\\\").replace('"', '\\"')[:900]
    script = (f'display dialog "{text}" buttons {{"Cancel", "Allow"}} '
              f'default button "Cancel" with title "Jarvis"')
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.returncode == 0 and "Allow" in r.stdout


class JarvisApp(rumps.App):
    def __init__(self):
        if os.path.exists(ICON):
            super().__init__("Jarvis", icon=ICON, template=False, quit_button=None)
        else:
            super().__init__("🤖", quit_button=None)
        self.cfg = Config(speak=True, voice=False)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._wake_thread = None
        self.voice = None
        self.safety = None
        self.agent = None

        self._hotkey = None
        self.menu = [
            "Ask Jarvis",
            "Stop current task",
            None,
            "Listen for wake word",
            "Auto-approve risky actions",
            "Speak replies",
            None,
            "Open log",
            "Quit Jarvis",
        ]
        self.menu["Speak replies"].state = True

    # ---- lazy setup (imports the SDK only when first needed) ----
    def _ensure_agent(self) -> bool:
        if self.agent:
            return True
        if not self.cfg.api_key:
            rumps.alert("Jarvis", "Set ANTHROPIC_API_KEY in a .env file first.")
            return False
        from agent import Agent
        from voice import Voice
        self.voice = Voice(voice_name=self.cfg.voice_name, listen=False)
        self.safety = SafetyManager(self.cfg.auto_approve, gui_confirm, LOG_PATH)
        self.agent = Agent(self.cfg, self.safety, on_text=self._notify,
                           voice=self.voice if self.cfg.speak else None)
        self._setup_hotkey()
        return True

    def _setup_hotkey(self) -> None:
        """Global stop hotkey: Cmd+Shift+. (optional — needs pynput)."""
        if self._hotkey:
            return
        try:
            from pynput import keyboard
            self._hotkey = keyboard.GlobalHotKeys({"<cmd>+<shift>+.": self._stop_task})
            self._hotkey.start()
        except Exception:
            self._hotkey = None  # pynput missing or no Accessibility — Stop menu still works

    def _stop_task(self) -> None:
        if self.agent:
            self.agent.cancel.set()
        rumps.notification("Jarvis", "", "Stopping…")

    def _notify(self, text: str) -> None:
        rumps.notification("Jarvis", "", text[:240])

    def _run(self, text: str) -> None:
        if not self._ensure_agent():
            return
        with self._lock:
            try:
                self.agent.run_turn(text)
            except Exception as e:
                rumps.notification("Jarvis", "error", str(e))

    # ---- menu actions ----
    @rumps.clicked("Ask Jarvis")
    def ask(self, _):
        if not self._ensure_agent():
            return
        win = rumps.Window(message="What should Jarvis do?", title="Jarvis",
                           dimensions=(360, 120), ok="Run", cancel="Cancel")
        resp = win.run()
        if resp.clicked and resp.text.strip():
            threading.Thread(target=self._run, args=(resp.text.strip(),),
                             daemon=True).start()

    @rumps.clicked("Stop current task")
    def stop_task(self, _):
        self._stop_task()

    @rumps.clicked("Listen for wake word")
    def toggle_listen(self, sender):
        if sender.state:
            self._stop.set()
            sender.state = False
        else:
            if not self._ensure_agent():
                return
            sender.state = True
            self._stop.clear()
            self._wake_thread = threading.Thread(target=self._wake_loop, daemon=True)
            self._wake_thread.start()

    def _wake_loop(self):
        from wake import WakeListener
        self.voice.speak("Listening.")
        WakeListener(self.cfg.wake_words, on_command=self._run,
                     speak=self.voice.speak).run(self._stop)

    @rumps.clicked("Auto-approve risky actions")
    def toggle_auto(self, sender):
        sender.state = not sender.state
        self.cfg.auto_approve = bool(sender.state)
        if self.safety:
            self.safety.auto_approve = self.cfg.auto_approve

    @rumps.clicked("Speak replies")
    def toggle_speak(self, sender):
        sender.state = not sender.state
        self.cfg.speak = bool(sender.state)
        if self.agent:
            self.agent.voice = self.voice if self.cfg.speak else None

    @rumps.clicked("Open log")
    def open_log(self, _):
        open(LOG_PATH, "a").close()
        subprocess.run(["open", LOG_PATH])

    @rumps.clicked("Quit Jarvis")
    def quit(self, _):
        self._stop.set()
        rumps.quit_application()


if __name__ == "__main__":
    JarvisApp().run()
