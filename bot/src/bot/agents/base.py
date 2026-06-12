"""Agent abstraction: one implementation per LLM backend (Claude, Gemini, ...)."""

from abc import ABC, abstractmethod


class Agent(ABC):
    """A conversational agent that keeps per-conversation context."""

    @abstractmethod
    async def reply(self, conversation_id: str, prompt: str) -> str:
        """Return the agent's reply to *prompt* within the given conversation.

        conversation_id groups messages into one continuous conversation
        (e.g. a Discord channel ID or Slack thread).
        """
