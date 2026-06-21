"""py2app build config for the Jarvis menu-bar app.

Build on your Mac:
    ./build_app.sh
which runs:
    python setup.py py2app
and produces dist/Jarvis.app (a background menu-bar app — no Dock icon).
"""
from setuptools import setup

APP = ["menubar.py"]

OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "CFBundleName": "Jarvis",
        "CFBundleDisplayName": "Jarvis",
        "CFBundleIdentifier": "com.local.jarvis",
        "CFBundleVersion": "1.0.0",
        "LSUIElement": True,  # menu-bar only, no Dock icon
        "NSMicrophoneUsageDescription":
            "Jarvis listens for the wake word and your spoken commands.",
        "NSAppleEventsUsageDescription":
            "Jarvis controls applications to carry out your requests.",
    },
    "packages": ["anthropic", "rumps", "certifi", "speech_recognition"],
    "includes": ["tools", "tools.extensions", "agent", "voice", "wake",
                 "config", "safety"],
}

setup(
    app=APP,
    name="Jarvis",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
