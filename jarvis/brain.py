"""Pick the brain: paid Claude (anthropic) or free local model (ollama)."""
from __future__ import annotations

from config import Config
from safety import SafetyManager


def build_agent(cfg: Config, safety: SafetyManager, on_text=print, voice=None):
    if cfg.provider == "ollama":
        from ollama_agent import OllamaAgent
        return OllamaAgent(cfg, safety, on_text=on_text, voice=voice)
    from agent import Agent
    return Agent(cfg, safety, on_text=on_text, voice=voice)
