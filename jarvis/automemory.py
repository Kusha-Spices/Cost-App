"""Automatically distil durable facts from a conversation into memory.

After each companion-mode exchange, the agent is asked (cheaply, no tools) to
extract anything worth remembering long-term about the user, and new items are
appended to memory. This is how Jarvis "learns" as you talk — by growing what it
knows about you, not by retraining the model.
"""
from __future__ import annotations

PROMPT = """From the exchange below, extract any NEW, durable facts worth remembering about the user long-term — their name, preferences, the people/projects/places in their life, habits, or how they like things done.

Rules:
- One short fact per line, in your own words (e.g. "Prefers concise answers").
- Only things that stay true over time. Ignore one-off task details and small talk.
- Skip anything already in EXISTING MEMORY.
- If there is nothing new worth saving, reply with exactly: NONE

EXISTING MEMORY:
{memory}

EXCHANGE:
User: {user}
Jarvis: {reply}
"""


def _dup(note: str, notes: list[str]) -> bool:
    n = note.lower()
    return any(n in e.lower() or e.lower() in n for e in notes)


def learn(agent, user_text: str, reply_text: str, max_new: int = 3) -> None:
    try:
        out = agent.quick_complete(PROMPT.format(
            memory=agent.memory.as_text() or "(empty)",
            user=user_text[:1500], reply=reply_text[:1500]))
    except Exception:
        return
    added = 0
    for line in (out or "").splitlines():
        note = line.strip(" -•\t").strip()
        if not note or note.upper() == "NONE":
            continue
        if _dup(note, agent.memory.all()):
            continue
        agent.memory.add(note)
        added += 1
        if added >= max_new:
            break
