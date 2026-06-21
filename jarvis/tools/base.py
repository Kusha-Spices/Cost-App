"""Shared tool primitives."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from safety import RiskLevel


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[..., Any]   # returns a str, or a list of API content blocks
    risk: RiskLevel = RiskLevel.SAFE

    def spec(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
