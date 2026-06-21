"""Launch and control macOS applications via `open` and AppleScript."""
from __future__ import annotations

import subprocess

from safety import RiskLevel
from tools.base import Tool


def open_app(name: str) -> str:
    r = subprocess.run(["open", "-a", name], capture_output=True, text=True)
    if r.returncode == 0:
        return f"Opened {name}."
    return f"Could not open {name}: {r.stderr.strip() or 'app not found'}"


def open_path(target: str) -> str:
    """Open a file, folder, or URL with its default application."""
    r = subprocess.run(["open", target], capture_output=True, text=True)
    if r.returncode == 0:
        return f"Opened {target}."
    return f"Could not open {target}: {r.stderr.strip()}"


def quit_app(name: str) -> str:
    r = subprocess.run(
        ["osascript", "-e", f'tell application "{name}" to quit'],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        return f"Asked {name} to quit."
    return f"Could not quit {name}: {r.stderr.strip()}"


def run_applescript(script: str) -> str:
    r = subprocess.run(["osascript", "-"], input=script, capture_output=True, text=True)
    out = r.stdout.strip()
    if r.returncode == 0:
        return out or "AppleScript ran successfully."
    return f"AppleScript error: {r.stderr.strip()}"


TOOLS = [
    Tool("open_app", "Launch a macOS application by name (e.g. 'Safari', 'Notes', 'Terminal').",
         {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
         open_app, RiskLevel.SAFE),
    Tool("open_path", "Open a file, folder, or URL with its default app.",
         {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]},
         open_path, RiskLevel.SAFE),
    Tool("quit_app", "Quit a running macOS application by name.",
         {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
         quit_app, RiskLevel.CAUTION),
    Tool("run_applescript",
         "Run an arbitrary AppleScript and return its output. Powerful — can script most "
         "Mac apps (Mail, Calendar, Music, Finder, System Events, etc.).",
         {"type": "object", "properties": {"script": {"type": "string"}}, "required": ["script"]},
         run_applescript, RiskLevel.DANGER),
]
