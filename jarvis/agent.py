"""The agent loop: Claude plans and calls tools until the task is done."""
from __future__ import annotations

import json

import anthropic

import tools as toolkit
from config import Config, MAX_AGENT_STEPS, system_prompt
from safety import SafetyManager

# Anthropic server-side tools — executed on Anthropic's side, no local handler.
WEB_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search"},
    {"type": "web_fetch_20260209", "name": "web_fetch"},
]


def _text_of(content) -> str:
    return "".join(b.text for b in content if getattr(b, "type", None) == "text").strip()


class Agent:
    def __init__(self, cfg: Config, safety: SafetyManager, on_text=print, voice=None):
        self.cfg = cfg
        self.safety = safety
        self.on_text = on_text
        self.voice = voice
        self.client = anthropic.Anthropic(api_key=cfg.api_key)
        self.system = system_prompt(cfg)
        self.messages: list[dict] = []
        self.tools = toolkit.specs() + (WEB_TOOLS if cfg.enable_web else [])

    def _create(self):
        kwargs = dict(
            model=self.cfg.model,
            max_tokens=self.cfg.max_tokens,
            system=self.system,
            tools=self.tools,
            messages=self.messages,
            output_config={"effort": self.cfg.effort},
        )
        if self.cfg.thinking:
            kwargs["thinking"] = {"type": "adaptive"}
        try:
            return self.client.messages.create(**kwargs)
        except TypeError:
            # Older SDK without thinking/output_config kwargs — degrade gracefully.
            kwargs.pop("thinking", None)
            kwargs.pop("output_config", None)
            return self.client.messages.create(**kwargs)

    def _run_tool(self, block) -> dict:
        tool = toolkit.REGISTRY.get(block.name)
        tool_input = block.input or {}
        if tool is None:
            return self._result(block.id, f"Unknown tool: {block.name}", is_error=True)

        preview = block.name + " " + json.dumps(tool_input, ensure_ascii=False)[:300]
        allowed, reason = self.safety.review(block.name, tool.risk, preview)
        if not allowed:
            return self._result(block.id, reason, is_error=True)
        try:
            result = tool.handler(**tool_input)
        except Exception as e:
            return self._result(block.id, f"Tool {block.name} failed: {e}", is_error=True)
        return self._result(block.id, result)

    @staticmethod
    def _result(tool_use_id: str, content, is_error: bool = False) -> dict:
        block = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
        if is_error:
            block["is_error"] = True
        return block

    def run_turn(self, user_text: str) -> str:
        self.messages.append({"role": "user", "content": user_text})
        final = ""

        for _ in range(MAX_AGENT_STEPS):
            resp = self._create()

            if resp.stop_reason == "refusal":
                final = ("I can't help with that one — it tripped a safety check. "
                         "Happy to help with something else.")
                self.messages.append({"role": "assistant", "content": resp.content})
                break

            text = _text_of(resp.content)
            if text:
                self.on_text(text)
            self.messages.append({"role": "assistant", "content": resp.content})

            if resp.stop_reason == "pause_turn":
                continue  # server-side tool needs another round — resend

            tool_uses = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
            if not tool_uses:
                final = text or "(I didn't produce a reply — try rephrasing.)"
                break

            results = [self._run_tool(b) for b in tool_uses]
            self.messages.append({"role": "user", "content": results})
        else:
            final = "Stopped: that took too many steps. Let's break it into smaller pieces."

        if self.voice and final:
            self.voice.speak(final)
        return final
