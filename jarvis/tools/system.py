"""System utilities: notifications, clipboard, volume, info."""
from __future__ import annotations

import subprocess

from safety import RiskLevel
from tools.base import Tool


def notify(title: str, message: str) -> str:
    safe_title = title.replace('"', "'")
    safe_msg = message.replace('"', "'")
    script = f'display notification "{safe_msg}" with title "{safe_title}"'
    subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return "Notification shown."


def get_clipboard(_note: str = "") -> str:
    r = subprocess.run(["pbpaste"], capture_output=True, text=True)
    return r.stdout or "(clipboard is empty)"


def set_clipboard(text: str) -> str:
    subprocess.run(["pbcopy"], input=text, text=True)
    return "Copied to clipboard."


def set_volume(level: int) -> str:
    level = max(0, min(100, int(level)))
    subprocess.run(["osascript", "-e", f"set volume output volume {level}"],
                   capture_output=True, text=True)
    return f"Set output volume to {level}%."


def system_info(_note: str = "") -> str:
    out = []
    for cmd in (["sw_vers"], ["uname", "-a"], ["uptime"]):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.stdout.strip():
            out.append(r.stdout.strip())
    return "\n".join(out) or "No info available."


TOOLS = [
    Tool("notify", "Show a macOS notification banner.",
         {"type": "object",
          "properties": {"title": {"type": "string"}, "message": {"type": "string"}},
          "required": ["title", "message"]},
         notify, RiskLevel.SAFE),
    Tool("get_clipboard", "Read the current clipboard contents.",
         {"type": "object", "properties": {}, "required": []},
         get_clipboard, RiskLevel.SAFE),
    Tool("set_clipboard", "Put text on the clipboard.",
         {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
         set_clipboard, RiskLevel.SAFE),
    Tool("set_volume", "Set the system output volume (0-100).",
         {"type": "object", "properties": {"level": {"type": "integer"}}, "required": ["level"]},
         set_volume, RiskLevel.SAFE),
    Tool("system_info", "Get macOS version, kernel, and uptime.",
         {"type": "object", "properties": {}, "required": []},
         system_info, RiskLevel.SAFE),
]
