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


def run_chat(cfg, agent, voice) -> int:
    """Companion conversation: warm back-and-forth that learns as you talk."""
    can_listen = bool(voice and voice.can_listen)
    greeting = "Hey, I'm here. What's on your mind?"
    print("Conversation mode — "
          + ("talk to me; say 'goodbye' to stop." if can_listen else "type to me; 'exit' to stop."))
    if voice and cfg.speak:
        voice.speak(greeting)
    print(f"\nJarvis: {greeting}\n")

    byes = ("goodbye", "bye", "exit", "quit", "stop talking", "that's all", "see you")
    while True:
        try:
            if can_listen:
                user = voice.listen()
                if not user:
                    continue
                print(f"You: {user}")
            else:
                user = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nTalk soon.")
            return 0

        if user.lower().strip(" .!") in byes:
            if voice and cfg.speak:
                voice.speak("Talk soon.")
            print("Talk soon.")
            return 0
        if not user:
            continue
        try:
            agent.run_turn(user)        # speaks the reply when voice is on
        except KeyboardInterrupt:
            print("\n(interrupted)")
        except Exception as e:
            print(f"[error] {e}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Jarvis — your Mac assistant.")
    ap.add_argument("--voice", action="store_true", help="Push-to-talk voice input.")
    ap.add_argument("--wake", action="store_true",
                    help="Always-listening wake word ('Jarvis ...').")
    ap.add_argument("--chat", action="store_true",
                    help="Companion conversation mode (warm, voice-to-voice, learns as you talk).")
    ap.add_argument("--no-speak", action="store_true", help="Disable spoken replies.")
    ap.add_argument("--no-web", action="store_true", help="Disable web search/fetch.")
    ap.add_argument("--auto", action="store_true",
                    help="Auto-approve risky actions (skips confirmation — use carefully).")
    ap.add_argument("--provider", default=None, choices=["anthropic", "ollama"],
                    help="anthropic = paid Claude; ollama = free local brain.")
    ap.add_argument("--model", default=None, help="Override the model id.")
    ap.add_argument("--effort", default=None,
                    choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--no-thinking", action="store_true", help="Disable extended thinking.")
    args = ap.parse_args()

    cfg = Config(voice=args.voice, auto_approve=args.auto)
    if args.provider:
        cfg.provider = args.provider
    if args.model:
        cfg.model = args.model
        cfg.ollama_model = args.model
    if args.effort:
        cfg.effort = args.effort
    if args.no_thinking:
        cfg.thinking = False
    if args.no_speak:
        cfg.speak = False
    if args.no_web:
        cfg.enable_web = False
    if args.chat:
        cfg.companion = True

    if cfg.provider == "anthropic" and not cfg.api_key:
        print("Set ANTHROPIC_API_KEY first (e.g. in a .env file), or use the free local "
              "brain with --provider ollama. See the README.")
        return 1

    want_listen = cfg.voice or args.chat
    voice = None
    if want_listen or cfg.speak:
        from voice import Voice
        voice = Voice(voice_name=cfg.voice_name, listen=want_listen, tts_cmd=cfg.tts_cmd)
        if cfg.voice and not voice.can_listen:
            print("Voice input unavailable — falling back to text. (Replies still spoken.)")
            cfg.voice = False

    speaking_voice = voice if cfg.speak else None

    from brain import build_agent  # imported here so --help works without deps installed
    safety = SafetyManager(cfg.auto_approve,
                           build_confirm(voice if cfg.voice else None), LOG_PATH)
    agent = build_agent(cfg, safety,
                        on_text=lambda t: print(f"\nJarvis: {t}\n"), voice=speaking_voice)

    if args.chat:
        return run_chat(cfg, agent, voice)

    if args.wake:
        return run_wake(cfg, agent, voice if cfg.speak else None)

    brain = f"local:{cfg.ollama_model}" if cfg.provider == "ollama" else f"claude:{cfg.model}"
    print(f"Jarvis is online (brain: {brain}). "
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
