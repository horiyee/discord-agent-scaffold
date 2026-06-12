from bot.agents.base import Agent
from bot.agents.claude import ClaudeAgent

__all__ = ["Agent", "ClaudeAgent", "create_agent"]


def create_agent(name: str) -> Agent:
    """Create an agent backend by name (e.g. "claude", later "gemini")."""
    if name == "claude":
        return ClaudeAgent()
    raise ValueError(f"unknown agent: {name!r}")
