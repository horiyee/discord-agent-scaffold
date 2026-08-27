from bot.agents.base import Agent
from bot.agents.claude import ClaudeAgent
from bot.agents.cursor import CursorAgent
from bot.agents.fugu import FuguAgent


def create_agent(name: str, *, model: str | None = None) -> Agent:
    """Create an agent backend by name (e.g. "claude", "cursor", "fugu")."""
    if name == "claude":
        return ClaudeAgent()
    if name == "cursor":
        return CursorAgent(model=model)
    if name == "fugu":
        return FuguAgent(model=model or "fugu")
    raise ValueError(f"unknown agent: {name!r}")
