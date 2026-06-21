"""Persistent memory — notes Jarvis keeps across sessions, in a local JSON file."""
from __future__ import annotations

import json
import threading


class Memory:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self.notes: list[str] = []
        self.load()

    def load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self.notes = [str(x) for x in data]
        except Exception:
            self.notes = []

    def _save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.notes, f, indent=2)
        except Exception:
            pass

    def add(self, note: str) -> int:
        with self._lock:
            self.notes.append(note.strip())
            self._save()
            return len(self.notes)

    def all(self) -> list[str]:
        return list(self.notes)

    def remove(self, index: int) -> str | None:
        with self._lock:
            if 0 <= index < len(self.notes):
                note = self.notes.pop(index)
                self._save()
                return note
        return None

    def as_text(self) -> str:
        return "\n".join(f"- {n}" for n in self.notes)
