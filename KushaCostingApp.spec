# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Kusha Costing App.

Builds a self-contained desktop app that bundles Python, Streamlit and all
dependencies, so the end user needs nothing installed. On macOS this produces
``Kusha Costing App.app``; on Linux/Windows it produces a one-folder build used
for verifying the packaging configuration.

Build:  pyinstaller KushaCostingApp.spec
"""

import sys
from PyInstaller.utils.hooks import collect_all, copy_metadata

block_cipher = None

# Streamlit ships frontend static files + uses importlib.metadata at runtime.
datas, binaries, hiddenimports = collect_all("streamlit")
for pkg in ("streamlit", "altair", "pandas", "numpy", "pyarrow", "openpyxl"):
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass

# Native window backend: pywebview + pyobjc (macOS WebKit). macOS only.
if sys.platform == "darwin":
    w_datas, w_binaries, w_hidden = collect_all("webview")
    datas += w_datas
    binaries += w_binaries
    hiddenimports += w_hidden
    hiddenimports += [
        "objc", "Foundation", "AppKit", "WebKit", "Quartz",
        "CoreFoundation", "Security",
    ]

# Native window backend on Windows: pywebview + pythonnet (WinForms / WebView2).
if sys.platform.startswith("win"):
    for pkg in ("webview", "pythonnet", "clr_loader"):
        try:
            p_datas, p_binaries, p_hidden = collect_all(pkg)
            datas += p_datas
            binaries += p_binaries
            hiddenimports += p_hidden
        except Exception:
            pass
    hiddenimports += [
        "clr",
        "webview.platforms.winforms",
        "webview.platforms.edgechromium",
        "webview.platforms.mshtml",
    ]

# The application source must be present so Streamlit can run app.py, plus the
# seed database/workbook.
app_modules = [
    "app.py",
    "database_engine.py",
    "v5_extensions.py",
    "v6_extensions.py",
    "v7_extensions.py",
    "v9_extensions.py",
    "v10_extensions.py",
]
datas += [(m, ".") for m in app_modules]
datas += [("data", "data")]

hiddenimports += [
    "database_engine",
    "v5_extensions",
    "v6_extensions",
    "v7_extensions",
    "v9_extensions",
    "v10_extensions",
    "pandas",
    "openpyxl",
    "pyarrow",
    "requests",
    "altair",
]

a = Analysis(
    ["run_app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # The app is fully local and does not use TLS crypto; excluding these heavy,
    # platform-sensitive packages keeps the bundle smaller and the build robust.
    excludes=["cryptography", "tkinter", "matplotlib", "PyQt5", "PySide2"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KushaCostingApp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="KushaCostingApp",
)

# macOS: wrap the one-folder build into a proper .app bundle.
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Kusha Costing App.app",
        icon=None,
        bundle_identifier="com.kushaspices.costingapp",
        version="9.2.0",
        info_plist={
            "CFBundleName": "Kusha Costing App",
            "CFBundleDisplayName": "Kusha Costing App",
            "CFBundleShortVersionString": "9.2",
            "CFBundleVersion": "9.2.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
