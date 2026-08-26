import os

from bot.agents.base import Agent
from bot.agents.claude import DEFAULT_MODEL, ClaudeAgent

__all__ = ["Agent", "ClaudeAgent", "create_agent"]


def create_agent(name: str) -> Agent:
    """Create an agent backend by name (e.g. "claude", later "gemini")."""
    if name == "claude":
        model = os.environ.get("BOT_MODEL", DEFAULT_MODEL)
        return ClaudeAgent(model=model)
    raise ValueError(f"unknown agent: {name!r}")
