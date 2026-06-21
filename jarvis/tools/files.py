"""Read, write, and manage files."""
from __future__ import annotations

import os

from safety import RiskLevel
from tools.base import Tool

MAX_READ = 100_000


def _p(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def read_file(path: str) -> str:
    fp = _p(path)
    try:
        with open(fp, "r", encoding="utf-8", errors="replace") as f:
            data = f.read(MAX_READ + 1)
    except FileNotFoundError:
        return f"No such file: {fp}"
    except IsADirectoryError:
        return f"{fp} is a directory. Use list_directory."
    except Exception as e:
        return f"Could not read {fp}: {e}"
    if len(data) > MAX_READ:
        return data[:MAX_READ] + f"\n…[truncated at {MAX_READ} chars]"
    return data or "(empty file)"


def write_file(path: str, content: str) -> str:
    fp = _p(path)
    try:
        os.makedirs(os.path.dirname(fp) or ".", exist_ok=True)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return f"Could not write {fp}: {e}"
    return f"Wrote {len(content)} chars to {fp}"


def append_file(path: str, content: str) -> str:
    fp = _p(path)
    try:
        with open(fp, "a", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return f"Could not append to {fp}: {e}"
    return f"Appended {len(content)} chars to {fp}"


def list_directory(path: str = ".") -> str:
    fp = _p(path)
    try:
        entries = sorted(os.listdir(fp))
    except Exception as e:
        return f"Could not list {fp}: {e}"
    if not entries:
        return f"{fp} is empty."
    lines = [fp + ":"]
    for name in entries[:500]:
        full = os.path.join(fp, name)
        if os.path.isdir(full):
            lines.append(f"  {name}/")
        else:
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            lines.append(f"  {name} ({size} bytes)")
    return "\n".join(lines)


def delete_path(path: str) -> str:
    fp = _p(path)
    try:
        if os.path.isdir(fp):
            os.rmdir(fp)  # empty dirs only — never recurse silently
            return f"Removed empty directory {fp}"
        os.remove(fp)
        return f"Deleted {fp}"
    except FileNotFoundError:
        return f"No such path: {fp}"
    except OSError as e:
        return (f"Could not delete {fp}: {e}. If it's a non-empty directory, remove its "
                "contents first or use run_shell.")


TOOLS = [
    Tool("read_file", "Read a text file and return its contents.",
         {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
         read_file, RiskLevel.SAFE),
    Tool("list_directory", "List the entries in a directory.",
         {"type": "object",
          "properties": {"path": {"type": "string", "description": "Defaults to current dir."}},
          "required": []},
         list_directory, RiskLevel.SAFE),
    Tool("write_file", "Create or overwrite a file with the given text content.",
         {"type": "object",
          "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
          "required": ["path", "content"]},
         write_file, RiskLevel.CAUTION),
    Tool("append_file", "Append text to the end of a file.",
         {"type": "object",
          "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
          "required": ["path", "content"]},
         append_file, RiskLevel.CAUTION),
    Tool("delete_path", "Delete a file or an empty directory.",
         {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
         delete_path, RiskLevel.DANGER),
]
