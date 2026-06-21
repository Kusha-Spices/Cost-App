"""Download files from the web.

Web *search* and *fetch* are provided by Anthropic's first-party server-side
tools (wired up in agent.py), which are more reliable than scraping. This module
adds local file download, which those server tools don't do.
"""
from __future__ import annotations

import os
import urllib.request

from safety import RiskLevel
from tools.base import Tool


def download_file(url: str, path: str) -> str:
    dest = os.path.abspath(os.path.expanduser(path))
    try:
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            f.write(r.read())
    except Exception as e:
        return f"Could not download {url}: {e}"
    return f"Downloaded {url} -> {dest} ({os.path.getsize(dest)} bytes)"


TOOLS = [
    Tool("download_file", "Download a file from a URL and save it to a local path.",
         {"type": "object",
          "properties": {"url": {"type": "string"}, "path": {"type": "string"}},
          "required": ["url", "path"]},
         download_file, RiskLevel.CAUTION),
]
