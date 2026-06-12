"""Claude agent backed by the Claude Agent SDK (Claude Code runtime)."""

import asyncio
from collections import defaultdict

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from bot.agents.base import Agent

DEFAULT_SYSTEM_PROMPT = (
    "あなたはチャットボットとして動作するアシスタントです。"
    "簡潔に、チャットに適した長さで日本語で答えてください。"
)


class ClaudeAgent(Agent):
    def __init__(self, model: str | None = None, system_prompt: str = DEFAULT_SYSTEM_PROMPT):
        self._model = model
        self._system_prompt = system_prompt
        # conversation_id -> Claude session_id (resumed on each turn)
        self._sessions: dict[str, str] = {}
        # Serialize turns per conversation so resume doesn't race
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def reply(self, conversation_id: str, prompt: str) -> str:
        async with self._locks[conversation_id]:
            options = ClaudeAgentOptions(
                model=self._model,
                system_prompt=self._system_prompt,
                resume=self._sessions.get(conversation_id),
            )
            parts: list[str] = []
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            parts.append(block.text)
                elif isinstance(message, ResultMessage):
                    self._sessions[conversation_id] = message.session_id
                    if message.is_error:
                        errors = "; ".join(message.errors or ["unknown error"])
                        return f"エラーが発生しました: {errors}"
            return "\n".join(parts)
