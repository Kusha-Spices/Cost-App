"""Free, local brain for Jarvis via Ollama (https://ollama.com).

Runs an open model entirely on the user's Mac — no API key, no cost. Talks to
Ollama's HTTP API directly (stdlib only), and reuses the same tools, safety
layer, and persistent memory as the Claude backend.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import automemory
import tools as toolkit
from config import Config, MAX_AGENT_STEPS, MEMORY_PATH, system_prompt
from memory import Memory
from safety import SafetyManager
from tools import memory as memory_tools


def _ollama_tools(specs: list[dict]) -> list[dict]:
    return [{"type": "function",
             "function": {"name": s["name"], "description": s["description"],
                          "parameters": s["input_schema"]}}
            for s in specs]


def _result_text(result) -> str:
    # Screenshot tools return image blocks; local models usually can't see, so
    # flatten to a short note instead.
    if isinstance(result, list):
        texts = [b.get("text", "") for b in result if isinstance(b, dict) and b.get("type") == "text"]
        return (" ".join(t for t in texts if t) or "[screenshot taken]") + \
               " (note: the local model can't view the image)."
    return str(result)


class OllamaAgent:
    def __init__(self, cfg: Config, safety: SafetyManager, on_text=print, voice=None):
        self.cfg = cfg
        self.safety = safety
        self.on_text = on_text
        self.voice = voice
        self.cancel = threading.Event()
        self.memory = Memory(MEMORY_PATH)
        memory_tools.bind(self.memory)
        self.tools = _ollama_tools(toolkit.specs())   # no server web tools locally
        self.messages: list[dict] = []

    def _chat(self, messages: list[dict]) -> dict:
        url = self.cfg.ollama_host.rstrip("/") + "/api/chat"
        body = json.dumps({"model": self.cfg.ollama_model, "messages": messages,
                           "tools": self.tools, "stream": False}).encode()
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read())

    def quick_complete(self, prompt: str) -> str:
        """One short, tool-less completion — used for auto-memory extraction."""
        url = self.cfg.ollama_host.rstrip("/") + "/api/chat"
        body = json.dumps({"model": self.cfg.ollama_model, "stream": False,
                           "messages": [
                               {"role": "system",
                                "content": "You extract durable facts to remember about the user. Be terse."},
                               {"role": "user", "content": prompt}]}).encode()
        try:
            req = urllib.request.Request(url, data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read()).get("message", {}).get("content", "")
        except Exception:
            return ""

    def _run_tool(self, name: str, args: dict) -> str:
        tool = toolkit.REGISTRY.get(name)
        if tool is None:
            return f"Unknown tool: {name}"
        preview = name + " " + json.dumps(args, ensure_ascii=False)[:300]
        allowed, reason = self.safety.review(name, tool.risk, preview)
        if not allowed:
            return reason
        try:
            return _result_text(tool.handler(**(args or {})))
        except Exception as e:
            return f"Tool {name} failed: {e}"

    def run_turn(self, user_text: str) -> str:
        self.cancel.clear()
        system = {"role": "system", "content": system_prompt(self.cfg, self.memory.as_text())}
        self.messages.append({"role": "user", "content": user_text})
        convo = [system] + self.messages
        final = ""

        for _ in range(MAX_AGENT_STEPS):
            if self.cancel.is_set():
                final = "Okay, stopped."
                break
            try:
                resp = self._chat(convo)
            except urllib.error.URLError:
                final = ("I can't reach the local brain. Make sure Ollama is installed and "
                         "running (open the Ollama app), then try again.")
                break
            except Exception as e:
                final = f"Local model error: {e}"
                break

            msg = resp.get("message", {}) or {}
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls") or []
            if content:
                self.on_text(content)

            entry = {"role": "assistant", "content": content}
            if tool_calls:
                entry["tool_calls"] = tool_calls
            convo.append(entry)
            self.messages.append(entry)

            if not tool_calls:
                final = content or "(no reply)"
                break

            if self.cancel.is_set():
                for tc in tool_calls:
                    convo.append({"role": "tool", "content": "Cancelled by the user."})
                final = "Okay, stopped."
                break

            for tc in tool_calls:
                fn = tc.get("function", {}) or {}
                name = fn.get("name", "")
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                result = self._run_tool(name, args)
                tool_msg = {"role": "tool", "content": result}
                convo.append(tool_msg)
                self.messages.append(tool_msg)
        else:
            final = "Stopped: that took too many steps. Let's try a smaller request."

        if final and self.cfg.companion and getattr(self.cfg, "auto_memory", True) \
                and not self.cancel.is_set():
            threading.Thread(target=automemory.learn, args=(self, user_text, final),
                             daemon=True).start()
        if self.voice and final:
            self.voice.speak(final)
        return final
