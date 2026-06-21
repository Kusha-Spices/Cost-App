"""Desktop entrypoint for the Kusha Costing App.

Launch flow (packaged app, double-clicked):

* The main process seeds a user-writable database on first run, picks a free
  port, starts the Streamlit server as a CHILD process, and shows the UI in a
  native window (pywebview / macOS WebKit). If the native window can't start, it
  falls back to opening the default browser, so the app is never worse than a
  browser tab.
* The child process (KUSHA_MODE=server) runs Streamlit on the main thread,
  which is required for its signal handlers.

Everything important is written to a log file (``launch.log``) so problems are
never silent, regardless of whether the windowed app has a usable console.

Works as a normal script (``python run_app.py``) and inside a PyInstaller
"frozen" bundle. ``--self-test`` just verifies the native-window backend is
importable and exits (used by CI).
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
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


def log(msg: str) -> None:
    """Write to the log file unconditionally, and to stdout if it works."""
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    try:
        print(line)
    except Exception:
        pass
    try:
        with open(log_path(), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def redirect_output_if_needed() -> None:
    """Some windowed builds set stdout/stderr to None; writing to them crashes
    Streamlit. Point them at the log file as a safety net."""
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
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def ensure_user_data() -> Path:
    data_dir = user_data_root() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    seed_dir = bundle_dir() / "data"
    for name in SEED_FILES:
        src = seed_dir / name
        dst = data_dir / name
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
    return data_dir


def show_error_dialog(message: str) -> None:
    if sys.platform != "darwin":
        return
    try:
        safe = message.replace('"', "'")[:400]
        subprocess.run(
            ["osascript", "-e", f'display dialog "{safe}" buttons {{"OK"}} with icon stop'],
            check=False,
        )
    except Exception:
        pass


def _port_is_free(port: str) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", int(port))) != 0


def choose_port() -> str:
    if os.environ.get("KUSHA_PORT"):
        return os.environ["KUSHA_PORT"]
    if _port_is_free(DEFAULT_PORT):
        return DEFAULT_PORT
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return str(s.getsockname()[1])


def wait_for_server(port: str, timeout: float = 90.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            if s.connect_ex(("127.0.0.1", int(port))) == 0:
                return True
        time.sleep(0.5)
    return False


def self_test() -> int:
    """Verify the native-window backend is importable from this build, including
    the macOS Cocoa/pyobjc backend (which pywebview loads lazily at runtime)."""
    try:
        import webview  # noqa: F401

        extra = ""
        if sys.platform == "darwin":
            import webview.platforms.cocoa  # noqa: F401  (imports AppKit/WebKit/pyobjc)

            extra = " cocoa+pyobjc OK"
        elif os.name == "nt":
            import clr  # noqa: F401  (pythonnet — required by the Windows WebView2 backend)

            extra = " pythonnet/clr OK"
        log(f"SELFTEST pywebview OK version={getattr(webview, '__version__', '?')}{extra}")
        return 0
    except Exception as exc:
        log(f"SELFTEST pywebview FAILED: {exc}")
        traceback.print_exc()
        return 3


def run_streamlit_server(port: str) -> int:
    """Child process: run Streamlit on the main thread (signal handlers need it)."""
    app_path = str(bundle_dir() / "app.py")
    sys.argv = [
        "streamlit", "run", app_path,
        "--server.port", str(port),
        "--server.address", "127.0.0.1",
        "--server.headless", "true",
        "--server.fileWatcherType", "none",
        "--browser.gatherUsageStats", "false",
        "--global.developmentMode", "false",
    ]
    from streamlit.web.cli import main as st_main

    return st_main()


def open_in_browser_and_wait(url: str, server_proc: subprocess.Popen) -> None:
    log(f"Opening in browser: {url}")
    try:
        webbrowser.open(url)
    except Exception:
        traceback.print_exc()
    try:
        server_proc.wait()
    except KeyboardInterrupt:
        pass


def show_window(url: str, server_proc: subprocess.Popen) -> None:
    """Show the UI in a native window; fall back to the browser on any problem."""
    try:
        import webview  # pywebview

        log("pywebview import OK")
    except Exception:
        log("pywebview not available; using browser.")
        traceback.print_exc()
        open_in_browser_and_wait(url, server_proc)
        return
    try:
        log("Showing native window")
        webview.create_window(APP_NAME, url, width=1280, height=860, min_size=(900, 600))
        webview.start()  # blocks until the window is closed
    except Exception:
        log("Native window failed to start; using browser.")
        traceback.print_exc()
        open_in_browser_and_wait(url, server_proc)


def run_window_mode() -> int:
    data_dir = ensure_user_data()
    os.environ["KUSHA_DATA_DIR"] = str(data_dir)
    port = choose_port()

    env = os.environ.copy()
    env["KUSHA_MODE"] = "server"
    env["KUSHA_PORT"] = str(port)
    env["KUSHA_DATA_DIR"] = str(data_dir)
    # Apply the warm "spice" theme regardless of the working directory (the
    # bundled .streamlit/config.toml is only picked up when run from the repo).
    env.setdefault("STREAMLIT_THEME_BASE", "light")
    env.setdefault("STREAMLIT_THEME_PRIMARY_COLOR", "#C0392B")
    env.setdefault("STREAMLIT_THEME_BACKGROUND_COLOR", "#FFFDF8")
    env.setdefault("STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR", "#FBEFE2")
    env.setdefault("STREAMLIT_THEME_TEXT_COLOR", "#2B2118")
    cmd = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, os.path.abspath(__file__)]

    log(f"Starting server on port {port}")
    popen_kwargs = {"env": env}
    if os.name == "nt":
        # Don't pop a console window for the child server on Windows.
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    server_proc = subprocess.Popen(cmd, **popen_kwargs)

    url = f"http://localhost:{port}"
    if not wait_for_server(port):
        msg = f"{APP_NAME}'s engine did not start in time.\n\nLog: {log_path()}"
        log(msg)
        show_error_dialog(msg)
        try:
            server_proc.terminate()
        except Exception:
            pass
        return 1

    try:
        show_window(url, server_proc)
    finally:
        try:
            server_proc.terminate()
            server_proc.wait(timeout=5)
        except Exception:
            try:
                server_proc.kill()
            except Exception:
                pass
    return 0


def main() -> int:
    redirect_output_if_needed()
    if "--self-test" in sys.argv or os.environ.get("KUSHA_MODE") == "selftest":
        return self_test()
    mode = os.environ.get("KUSHA_MODE", "window")
    log(f"=== {APP_NAME} starting ({time.ctime()}) mode={mode} ===")
    if mode == "server":
        ensure_user_data()
        return run_streamlit_server(os.environ.get("KUSHA_PORT", DEFAULT_PORT))
    return run_window_mode()


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
            log("FATAL: " + "".join(traceback.format_exc()))
        except Exception:
            pass
        show_error_dialog(f"{APP_NAME} could not start.\n\nLog: {log_path()}")
        raise
