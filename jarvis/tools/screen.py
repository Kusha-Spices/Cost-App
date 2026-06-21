"""See and control the screen: screenshots, mouse, and keyboard."""
from __future__ import annotations

import base64
import os
import subprocess
import time

from config import SCREENSHOT_DIR
from safety import RiskLevel
from tools.base import Tool

MAX_IMG_EDGE = 1568  # keep image tokens/cost reasonable


def _pyautogui():
    import pyautogui  # lazy: only needed at runtime on the Mac
    pyautogui.FAILSAFE = True
    return pyautogui


def take_screenshot(_note: str = ""):
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    path = os.path.join(SCREENSHOT_DIR, f"shot_{int(time.time())}.png")
    r = subprocess.run(["screencapture", "-x", path], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(path):
        return ("Could not capture the screen: " + (r.stderr.strip() or "unknown error") +
                ". Grant Screen Recording permission in System Settings → Privacy & Security.")
    try:
        from PIL import Image
        img = Image.open(path)
        if max(img.size) > MAX_IMG_EDGE:
            img.thumbnail((MAX_IMG_EDGE, MAX_IMG_EDGE))
            img.convert("RGB").save(path)
    except Exception:
        pass  # Pillow optional; send full-size if unavailable
    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode()
    return [
        {"type": "text", "text": f"Screenshot saved to {path}. Current screen:"},
        {"type": "image",
         "source": {"type": "base64", "media_type": "image/png", "data": data}},
    ]


def get_screen_size(_note: str = "") -> str:
    w, h = _pyautogui().size()
    return f"Screen size is {w}x{h} pixels."


def mouse_click(x: int, y: int, button: str = "left", clicks: int = 1) -> str:
    _pyautogui().click(x=x, y=y, clicks=clicks, button=button)
    return f"Clicked {button} x{clicks} at ({x}, {y})."


def type_text(text: str) -> str:
    _pyautogui().typewrite(text, interval=0.01)
    return f"Typed {len(text)} characters."


def press_keys(keys: str) -> str:
    """Press a key or a combo like 'cmd+space', 'enter', 'cmd+shift+4'."""
    pg = _pyautogui()
    alias = {"cmd": "command", "opt": "option", "ctrl": "control",
             "esc": "escape", "win": "command", "return": "enter"}
    parts = [alias.get(k.strip().lower(), k.strip().lower()) for k in keys.split("+")]
    if len(parts) == 1:
        pg.press(parts[0])
    else:
        pg.hotkey(*parts)
    return f"Pressed {keys}."


def scroll(amount: int) -> str:
    _pyautogui().scroll(amount)
    return f"Scrolled {amount}."


TOOLS = [
    Tool("take_screenshot",
         "Capture the screen and look at it. Use this to see what's currently displayed "
         "before deciding where to click or type, and to verify results.",
         {"type": "object", "properties": {}, "required": []},
         take_screenshot, RiskLevel.SAFE),
    Tool("get_screen_size", "Get the screen dimensions in pixels.",
         {"type": "object", "properties": {}, "required": []},
         get_screen_size, RiskLevel.SAFE),
    Tool("mouse_click", "Move the mouse to (x, y) and click.",
         {"type": "object",
          "properties": {"x": {"type": "integer"}, "y": {"type": "integer"},
                         "button": {"type": "string", "enum": ["left", "right", "middle"]},
                         "clicks": {"type": "integer", "description": "1=single, 2=double"}},
          "required": ["x", "y"]},
         mouse_click, RiskLevel.CAUTION),
    Tool("type_text", "Type text at the current cursor/focus.",
         {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
         type_text, RiskLevel.CAUTION),
    Tool("press_keys", "Press a key or shortcut, e.g. 'enter', 'cmd+space', 'cmd+c'.",
         {"type": "object", "properties": {"keys": {"type": "string"}}, "required": ["keys"]},
         press_keys, RiskLevel.CAUTION),
    Tool("scroll", "Scroll the mouse wheel; positive scrolls up, negative down.",
         {"type": "object", "properties": {"amount": {"type": "integer"}}, "required": ["amount"]},
         scroll, RiskLevel.CAUTION),
]
