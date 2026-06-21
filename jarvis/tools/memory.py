"""Tools that let Jarvis remember things across sessions.

The store is bound at startup by the agent (see agent.py -> bind()). Remembered
notes are also injected into Jarvis's system prompt each turn, so it recalls
them automatically without having to call `recall`.
"""
from __future__ import annotations

from safety import RiskLevel
from tools.base import Tool

_store = None


def bind(store) -> None:
    global _store
    _store = store


def remember(note: str) -> str:
    if _store is None:
        return "Memory isn't available."
    n = _store.add(note)
    return f"Got it — I'll remember that (note #{n - 1})."


def recall(_note: str = "") -> str:
    if _store is None:
        return "Memory isn't available."
    items = _store.all()
    if not items:
        return "I haven't been asked to remember anything yet."
    return "\n".join(f"{i}. {t}" for i, t in enumerate(items))


def forget(index: int) -> str:
    if _store is None:
        return "Memory isn't available."
    note = _store.remove(int(index))
    return f"Forgot: {note}" if note is not None else "No memory at that index."


TOOLS = [
    Tool("remember",
         "Save a fact or preference to remember in future sessions (e.g. the user's name, "
         "preferred editor, project paths).",
         {"type": "object", "properties": {"note": {"type": "string"}}, "required": ["note"]},
         remember, RiskLevel.SAFE),
    Tool("recall", "List everything remembered so far.",
         {"type": "object", "properties": {}, "required": []},
         recall, RiskLevel.SAFE),
    Tool("forget", "Remove a remembered note by its index (see recall).",
         {"type": "object", "properties": {"index": {"type": "integer"}}, "required": ["index"]},
         forget, RiskLevel.SAFE),
]
