"""Run shell commands on the user's machine."""
from __future__ import annotations

import subprocess

from safety import RiskLevel
from tools.base import Tool

MAX_OUTPUT = 12000


def _truncate(s: str) -> str:
    if len(s) > MAX_OUTPUT:
        return s[:MAX_OUTPUT] + f"\n…[truncated {len(s) - MAX_OUTPUT} chars]"
    return s


def run_shell(command: str, timeout: int = 60) -> str:
    try:
        proc = subprocess.run(
            ["/bin/bash", "-lc", command],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s."
    except Exception as e:
        return f"Failed to run command: {e}"

    parts = [f"exit code: {proc.returncode}"]
    if proc.stdout.strip():
        parts.append("stdout:\n" + _truncate(proc.stdout))
    if proc.stderr.strip():
        parts.append("stderr:\n" + _truncate(proc.stderr))
    return "\n".join(parts)


TOOLS = [
    Tool(
        name="run_shell",
        description=(
            "Run a bash command on the user's Mac and return its exit code, stdout, and "
            "stderr. Use this for anything a terminal can do: CLI tools, file management, "
            "git, package managers, querying system state. Prefer this over screen control "
            "whenever an equivalent command exists."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The bash command to run."},
                "timeout": {"type": "integer", "description": "Max seconds to wait (default 60)."},
            },
            "required": ["command"],
        },
        handler=run_shell,
        risk=RiskLevel.DANGER,
    ),
]
