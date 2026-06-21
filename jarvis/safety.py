"""Risk classification, confirmation, and logging for tool calls."""
from __future__ import annotations

import enum
import re
from datetime import datetime
from typing import Callable


class RiskLevel(enum.IntEnum):
    SAFE = 0      # read-only / trivially reversible — runs without asking
    CAUTION = 1   # writes, app/screen control — confirm in guarded mode
    DANGER = 2    # deletion, arbitrary shell/AppleScript — confirm in guarded mode


# Catastrophic, near-irreversible commands. Denied in EVERY mode (even --auto)
# as a last-resort safety net; Jarvis is told and can pick another approach.
HARD_BLOCK = [
    r"\brm\s+-[a-z]*r[a-z]*f[a-z]*\s+(/|~|/\*|\$HOME)(\s|$)",
    r"\brm\s+-[a-z]*f[a-z]*r[a-z]*\s+(/|~|/\*|\$HOME)(\s|$)",
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",   # fork bomb
    r"\bmkfs\b",
    r"\bdd\b.*\bof=/dev/",
    r">\s*/dev/(sd|disk|nvme)",
    r"\bchmod\s+-[a-z]*R[a-z]*\s+0+\s+/",
]

# Patterns worth flagging in the confirmation prompt (not auto-denied).
RISKY_HINTS = [
    (r"\brm\s+-[a-z]*r", "recursive delete"),
    (r"\bsudo\b", "runs as administrator"),
    (r"\bshutdown\b|\breboot\b", "powers off / restarts the machine"),
    (r"\b(curl|wget)\b.*\|\s*(sh|bash|zsh)", "pipes a download straight into a shell"),
    (r">\s*/(?!Users|tmp|var/folders)", "overwrites a system path"),
]


class SafetyManager:
    def __init__(self, auto_approve: bool, confirm: Callable[[str], bool], log_path: str):
        self.auto_approve = auto_approve
        self._confirm = confirm
        self.log_path = log_path

    def log(self, line: str) -> None:
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat(timespec='seconds')}  {line}\n")
        except Exception:
            pass

    def _hard_blocked(self, text: str) -> bool:
        return any(re.search(p, text, re.IGNORECASE) for p in HARD_BLOCK)

    def _hints(self, text: str) -> list[str]:
        return [why for pat, why in RISKY_HINTS if re.search(pat, text, re.IGNORECASE)]

    def review(self, name: str, risk: RiskLevel, preview: str) -> tuple[bool, str]:
        """Return (allowed, reason). May prompt the user for confirmation."""
        if self._hard_blocked(preview):
            self.log(f"HARD-BLOCK {name}: {preview}")
            return False, ("Refused: this looks catastrophic and irreversible. I won't run "
                           "it. Tell me a safer goal and I'll find another way.")

        if risk == RiskLevel.SAFE or self.auto_approve:
            self.log(f"ALLOW{' (auto)' if self.auto_approve else ''} [{risk.name}] {name}: {preview}")
            return True, ""

        hints = self._hints(preview)
        warn = f"\n    ⚠ {', '.join(hints)}" if hints else ""
        prompt = f"\nJarvis wants to run [{risk.name}] {name}:\n    {preview}{warn}\nAllow? [y/N] "
        ok = bool(self._confirm(prompt))
        self.log(f"{'ALLOW' if ok else 'DENY'} [{risk.name}] {name}: {preview}")
        if not ok:
            return False, "The user declined this action. Suggest a safer alternative."
        return True, ""
