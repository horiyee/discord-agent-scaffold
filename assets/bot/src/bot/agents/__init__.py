from bot.agents.base import Agent
from bot.agents.claude import ClaudeAgent
from bot.agents.fugu import FuguAgent

__all__ = ["Agent", "ClaudeAgent", "FuguAgent", "create_agent"]


def create_agent(name: str) -> Agent:
    """Create an agent backend by name (e.g. "claude", "fugu")."""
    if name == "claude":
        return ClaudeAgent()
    if name == "fugu":
        return FuguAgent()
    raise ValueError(f"unknown agent: {name!r}")
