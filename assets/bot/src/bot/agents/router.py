"""Routes conversations to the selected agent backend at runtime."""

from __future__ import annotations

import logging

from bot.agents.base import Agent
from bot.agents.factory import create_agent
from bot.model_selection import ModelSelection, ModelSelectionStore

logger = logging.getLogger(__name__)


class AgentRouter(Agent):
    """Delegates replies to per-conversation model selections."""

    def __init__(self, store: ModelSelectionStore | None = None):
        self._store = store or ModelSelectionStore()
        self._agents: dict[str, Agent] = {}

    @property
    def store(self) -> ModelSelectionStore:
        return self._store

    def _get_agent(self, selection: ModelSelection) -> Agent:
        cached = self._agents.get(selection.key)
        if cached is not None:
            return cached
        agent = create_agent(selection.agent, model=selection.model)
        self._agents[selection.key] = agent
        logger.info("initialized agent backend %s", selection.label())
        return agent

    async def reply(self, conversation_id: str, prompt: str) -> str:
        selection = self._store.get(conversation_id)
        agent = self._get_agent(selection)
        scoped_id = self._store.scoped_conversation_id(conversation_id, selection)
        return await agent.reply(scoped_id, prompt)
