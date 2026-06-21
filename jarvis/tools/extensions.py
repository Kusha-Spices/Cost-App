"""High-level extensions: common macOS apps + an Apple Shortcuts bridge.

These are conveniences built on AppleScript / the `shortcuts` CLI so Jarvis
doesn't have to hand-write a script for everyday tasks. The universal escape
hatches remain `run_shell` (any execution) and `run_applescript` (any app) —
if a tool here doesn't fit, Jarvis falls back to those.
"""
from __future__ import annotations

import subprocess

from safety import RiskLevel
from tools.base import Tool


def _esc(s: str) -> str:
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


def _osa(script: str) -> tuple[int, str, str]:
    r = subprocess.run(["osascript", "-"], input=script, capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _run_osa(script: str, ok: str) -> str:
    rc, out, err = _osa(script)
    if rc == 0:
        return out or ok
    return f"AppleScript error: {err}"


# ---- Apple Shortcuts: the universal extension bridge --------------------------

def list_shortcuts(_note: str = "") -> str:
    r = subprocess.run(["shortcuts", "list"], capture_output=True, text=True)
    return r.stdout.strip() or "No shortcuts found (or Shortcuts not available)."


def run_shortcut(name: str, input: str = "") -> str:
    try:
        if input:
            r = subprocess.run(["shortcuts", "run", name, "-i", "-"],
                               input=input, capture_output=True, text=True)
        else:
            r = subprocess.run(["shortcuts", "run", name],
                               capture_output=True, text=True)
    except FileNotFoundError:
        return "The `shortcuts` CLI isn't available on this macOS version."
    if r.returncode == 0:
        return r.stdout.strip() or f"Ran shortcut '{name}'."
    return f"Shortcut '{name}' failed: {r.stderr.strip()}"


# ---- Productivity apps --------------------------------------------------------

def send_email(to: str, subject: str, body: str) -> str:
    script = f'''
tell application "Mail"
    set msg to make new outgoing message with properties {{subject:"{_esc(subject)}", content:"{_esc(body)}", visible:true}}
    tell msg to make new to recipient at end of to recipients with properties {{address:"{_esc(to)}"}}
    send msg
end tell'''
    return _run_osa(script, f"Email sent to {to}.")


def create_reminder(text: str) -> str:
    script = f'tell application "Reminders" to make new reminder with properties {{name:"{_esc(text)}"}}'
    return _run_osa(script, f"Reminder added: {text}")


def create_note(title: str, body: str = "") -> str:
    script = (f'tell application "Notes" to make new note with properties '
              f'{{name:"{_esc(title)}", body:"{_esc(body)}"}}')
    return _run_osa(script, f"Note created: {title}")


def calendar_add_event(title: str, start: str, duration_minutes: int = 60) -> str:
    """start is a date string in your locale, e.g. 'March 3, 2026 3:00 PM'."""
    script = f'''
set theStart to date "{_esc(start)}"
set theEnd to theStart + ({int(duration_minutes)} * minutes)
tell application "Calendar"
    tell calendar 1
        make new event with properties {{summary:"{_esc(title)}", start date:theStart, end date:theEnd}}
    end tell
end tell'''
    return _run_osa(script, f"Event '{title}' added at {start}.")


def music_control(action: str, app: str = "Music") -> str:
    cmds = {"play": "play", "pause": "pause", "playpause": "playpause",
            "toggle": "playpause", "next": "next track",
            "previous": "previous track", "prev": "previous track"}
    cmd = cmds.get(action.lower())
    if not cmd:
        return f"Unknown action '{action}'. Use play/pause/next/previous."
    if app not in ("Music", "Spotify"):
        return "app must be 'Music' or 'Spotify'."
    return _run_osa(f'tell application "{app}" to {cmd}', f"{app}: {action}")


# ---- Generic UI control (works for *any* app) ---------------------------------

def keystroke_to(app: str, text: str, modifiers: list | None = None) -> str:
    using = ""
    if modifiers:
        mods = ", ".join(f"{m} down" for m in modifiers)
        using = f" using {{{mods}}}"
    script = f'''
tell application "{_esc(app)}" to activate
delay 0.2
tell application "System Events" to keystroke "{_esc(text)}"{using}'''
    return _run_osa(script, f"Sent '{text}' to {app}.")


def menu_click(app: str, menu: str, item: str) -> str:
    script = f'''
tell application "{_esc(app)}" to activate
delay 0.2
tell application "System Events" to tell process "{_esc(app)}"
    click menu item "{_esc(item)}" of menu "{_esc(menu)}" of menu bar item "{_esc(menu)}" of menu bar 1
end tell'''
    return _run_osa(script, f"Clicked {menu} > {item} in {app}.")


TOOLS = [
    Tool("list_shortcuts", "List the user's Apple Shortcuts (each is a callable automation).",
         {"type": "object", "properties": {}, "required": []},
         list_shortcuts, RiskLevel.SAFE),
    Tool("run_shortcut",
         "Run an Apple Shortcut by name, optionally passing text input. Shortcuts can do "
         "almost anything the user has wired up (smart home, web APIs, file tasks, etc.).",
         {"type": "object",
          "properties": {"name": {"type": "string"},
                         "input": {"type": "string", "description": "Optional text input."}},
          "required": ["name"]},
         run_shortcut, RiskLevel.CAUTION),
    Tool("send_email", "Send an email via the Mail app.",
         {"type": "object",
          "properties": {"to": {"type": "string"}, "subject": {"type": "string"},
                         "body": {"type": "string"}},
          "required": ["to", "subject", "body"]},
         send_email, RiskLevel.DANGER),
    Tool("create_reminder", "Add a reminder in the Reminders app.",
         {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
         create_reminder, RiskLevel.CAUTION),
    Tool("create_note", "Create a note in the Notes app.",
         {"type": "object",
          "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
          "required": ["title"]},
         create_note, RiskLevel.CAUTION),
    Tool("calendar_add_event",
         "Add a calendar event. 'start' is a locale date string like 'March 3, 2026 3:00 PM'.",
         {"type": "object",
          "properties": {"title": {"type": "string"}, "start": {"type": "string"},
                         "duration_minutes": {"type": "integer"}},
          "required": ["title", "start"]},
         calendar_add_event, RiskLevel.CAUTION),
    Tool("music_control", "Control Music or Spotify: play, pause, next, previous.",
         {"type": "object",
          "properties": {"action": {"type": "string",
                                    "enum": ["play", "pause", "playpause", "next", "previous"]},
                         "app": {"type": "string", "enum": ["Music", "Spotify"]}},
          "required": ["action"]},
         music_control, RiskLevel.SAFE),
    Tool("keystroke_to",
         "Activate an app and send a keystroke/shortcut to it. modifiers is a list like "
         "['command'] or ['command','shift'].",
         {"type": "object",
          "properties": {"app": {"type": "string"}, "text": {"type": "string"},
                         "modifiers": {"type": "array", "items": {"type": "string"}}},
          "required": ["app", "text"]},
         keystroke_to, RiskLevel.CAUTION),
    Tool("menu_click",
         "Click a menu-bar menu item in any app, e.g. app='Safari', menu='File', item='New Window'.",
         {"type": "object",
          "properties": {"app": {"type": "string"}, "menu": {"type": "string"},
                         "item": {"type": "string"}},
          "required": ["app", "menu", "item"]},
         menu_click, RiskLevel.CAUTION),
]
