"""Jarvis — a local voice + text assistant for your Mac, powered by Claude.

Run:  python main.py            # text in, spoken + printed replies
      python main.py --voice    # push-to-talk voice in, spoken replies
      python main.py --help      # all options
"""
from __future__ import annotations

import argparse
import sys

from config import Config, LOG_PATH
from safety import SafetyManager


def build_confirm(voice):
    def confirm(prompt: str) -> bool:
        if voice:
            voice.speak("I need your okay for something.")
        try:
            return input(prompt).strip().lower() in ("y", "yes")
        except EOFError:
            return False
    return confirm


def run_wake(cfg, agent, voice) -> int:
    """Always-listening mode: say 'Jarvis ...' to issue a command."""
    import threading

    from wake import WakeListener

    stop = threading.Event()
    speak = voice.speak if voice else None

    def on_cmd(text: str) -> None:
        print(f"\nYou: {text}")
        agent.run_turn(text)

    print("Listening for the wake word. Say 'Jarvis …' to give a command. Ctrl-C to quit.")
    if speak:
        speak("Jarvis online.")
    try:
        WakeListener(cfg.wake_words, on_command=on_cmd, speak=speak).run(stop)
    except KeyboardInterrupt:
        stop.set()
        print("\nBye.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Jarvis — your Mac assistant.")
    ap.add_argument("--voice", action="store_true", help="Push-to-talk voice input.")
    ap.add_argument("--wake", action="store_true",
                    help="Always-listening wake word ('Jarvis ...').")
    ap.add_argument("--no-speak", action="store_true", help="Disable spoken replies.")
    ap.add_argument("--no-web", action="store_true", help="Disable web search/fetch.")
    ap.add_argument("--auto", action="store_true",
                    help="Auto-approve risky actions (skips confirmation — use carefully).")
    ap.add_argument("--model", default=None, help="Override the model id.")
    ap.add_argument("--effort", default=None,
                    choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--no-thinking", action="store_true", help="Disable extended thinking.")
    args = ap.parse_args()

    cfg = Config(voice=args.voice, auto_approve=args.auto)
    if args.model:
        cfg.model = args.model
    if args.effort:
        cfg.effort = args.effort
    if args.no_thinking:
        cfg.thinking = False
    if args.no_speak:
        cfg.speak = False
    if args.no_web:
        cfg.enable_web = False

    if not cfg.api_key:
        print("Set ANTHROPIC_API_KEY first (e.g. in a .env file). See the README.")
        return 1

    voice = None
    if cfg.voice or cfg.speak:
        from voice import Voice
        voice = Voice(voice_name=cfg.voice_name, listen=cfg.voice)
        if cfg.voice and not voice.can_listen:
            print("Voice input unavailable — falling back to text. (Replies still spoken.)")
            cfg.voice = False

    speaking_voice = voice if cfg.speak else None

    from agent import Agent  # imported here so --help works without the SDK installed
    safety = SafetyManager(cfg.auto_approve,
                           build_confirm(voice if cfg.voice else None), LOG_PATH)
    agent = Agent(cfg, safety,
                  on_text=lambda t: print(f"\nJarvis: {t}\n"), voice=speaking_voice)

    if args.wake:
        return run_wake(cfg, agent, voice if cfg.speak else None)

    print("Jarvis is online. "
          + ("Press Enter to talk, or just type. " if cfg.voice else "")
          + "Type 'exit' to quit.")
    if cfg.auto_approve:
        print("⚠  Auto-approve is ON — Jarvis will run risky actions without asking.")

    while True:
        try:
            if cfg.voice:
                input("\n[Enter to speak] ")
                print("Listening…")
                user = voice.listen()
                print(f"You: {user}" if user else "(didn't catch that)")
                if not user:
                    continue
            else:
                user = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return 0

        if user.lower() in ("exit", "quit", "bye"):
            print("Bye.")
            return 0
        if not user:
            continue

        try:
            agent.run_turn(user)
        except KeyboardInterrupt:
            print("\n(interrupted)")
        except Exception as e:
            print(f"[error] {e}")


if __name__ == "__main__":
    sys.exit(main())
