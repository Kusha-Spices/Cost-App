"""Desktop entrypoint for the Kusha Costing App.

This is what a packaged Mac/Windows app (or a local launcher) runs. It:

* picks a user-writable folder for the live SQLite database,
* seeds it from the bundled database on first launch (and never overwrites it
  afterwards, so your edits survive app updates),
* opens the browser, and
* starts the Streamlit server.

It works both as a normal script (``python run_app.py``) and inside a
PyInstaller "frozen" bundle.
"""

from __future__ import annotations

import os
import shutil
import sys
import threading
import time
import webbrowser
from pathlib import Path

APP_NAME = "Kusha Costing App"
SEED_FILES = ["kusha_costing_v8.3.sqlite", "Cost Sheet 2026 new(3).xlsx"]
DEFAULT_PORT = "8501"


def bundle_dir() -> Path:
    """Directory that holds the bundled code and seed data."""
    if getattr(sys, "frozen", False):
        # PyInstaller unpacks bundled files to _MEIPASS.
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def user_data_root() -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        root = home / "Library" / "Application Support" / APP_NAME
    elif os.name == "nt":
        root = Path(os.environ.get("APPDATA", home)) / APP_NAME
    else:
        root = home / ".kusha_costing_app"
    root.mkdir(parents=True, exist_ok=True)
    return root


def ensure_user_data() -> Path:
    """Create the writable data dir and seed it from the bundle if empty."""
    data_dir = user_data_root() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    seed_dir = bundle_dir() / "data"
    for name in SEED_FILES:
        src = seed_dir / name
        dst = data_dir / name
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
    return data_dir


def open_browser_when_ready(url: str) -> None:
    def _open() -> None:
        time.sleep(3)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=_open, daemon=True).start()


def main() -> int:
    base = bundle_dir()
    data_dir = ensure_user_data()
    os.environ["KUSHA_DATA_DIR"] = str(data_dir)

    port = os.environ.get("KUSHA_PORT", DEFAULT_PORT)
    open_browser_when_ready(f"http://localhost:{port}")

    app_path = str(base / "app.py")
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--server.port",
        port,
        "--server.headless",
        "true",
        "--server.fileWatcherType",
        "none",
        "--browser.gatherUsageStats",
        "false",
        "--global.developmentMode",
        "false",
    ]

    from streamlit.web.cli import main as st_main

    return st_main()


if __name__ == "__main__":
    raise SystemExit(main())
