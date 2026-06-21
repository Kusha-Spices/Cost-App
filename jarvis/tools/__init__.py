"""Aggregate every Tool into a registry the agent can use."""
from __future__ import annotations

from tools import apps, extensions, files, screen, shell, system, web
from tools.base import Tool

ALL_TOOLS: list[Tool] = []
for _mod in (shell, files, apps, screen, web, system, extensions):
    ALL_TOOLS.extend(_mod.TOOLS)

REGISTRY: dict[str, Tool] = {t.name: t for t in ALL_TOOLS}


def specs() -> list[dict]:
    """Anthropic tool specs for every client-side tool."""
    return [t.spec() for t in ALL_TOOLS]
