"""Desktop entrypoint for the Kusha Costing App.

This is what a packaged Mac/Windows app (or a local launcher) runs. It:

* makes output safe when launched from Finder (a windowed app has no console, so
  ``sys.stdout``/``sys.stderr`` are ``None`` — writing to them crashes Streamlit;
  we redirect them to a log file),
* picks a user-writable folder for the live SQLite database and seeds it on first
  launch (so your edits survive app updates),
* opens the browser, and
* starts the Streamlit server,
* and on any startup failure, records a crash log and shows a dialog instead of
  silently disappearing.

Works both as a normal script (``python run_app.py``) and inside a PyInstaller
"frozen" bundle.
"""

from __future__ import annotations

import os
import shutil
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

APP_NAME = "Kusha Costing App"
SEED_FILES = ["kusha_costing_v8.3.sqlite", "Cost Sheet 2026 new(3).xlsx"]
DEFAULT_PORT = "8501"


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


def log_path() -> Path:
    return user_data_root() / "launch.log"


def redirect_output_if_needed() -> None:
    """A windowed (.app) launch has no console: stdout/stderr are None, which
    makes Streamlit/Click crash on startup. Send them to a log file instead."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        stream = open(log_path(), "a", buffering=1, encoding="utf-8")
    except Exception:
        stream = open(os.devnull, "w")
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


def bundle_dir() -> Path:
    """Directory that holds the bundled code and seed data."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


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


def show_error_dialog(message: str) -> None:
    if sys.platform != "darwin":
        return
    try:
        import subprocess

        safe = message.replace('"', "'")[:400]
        subprocess.run(
            ["osascript", "-e", f'display dialog "{safe}" buttons {{"OK"}} with icon stop'],
            check=False,
        )
    except Exception:
        pass


def main() -> int:
    redirect_output_if_needed()
    print(f"\n=== {APP_NAME} starting at {time.ctime()} ===")

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
    try:
        import multiprocessing

        multiprocessing.freeze_support()
    except Exception:
        pass
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001 - last-resort crash handler
        try:
            redirect_output_if_needed()
            traceback.print_exc()
        except Exception:
            pass
        show_error_dialog(
            f"{APP_NAME} could not start.\n\nA log was saved to:\n{log_path()}\n\n"
            "Please share that file so the problem can be fixed."
        )
        raise
