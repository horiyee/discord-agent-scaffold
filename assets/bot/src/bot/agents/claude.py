"""Claude agent backed by the Claude Agent SDK (Claude Code runtime)."""

import asyncio
import logging
import os
from collections import defaultdict

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from bot.agents.base import Agent
from mcp_servers import agent_options, enabled_servers, system_prompt_suffix

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-4-6"
DEFAULT_ALLOWED_TOOLS = ("WebSearch", "WebFetch")

DEFAULT_SYSTEM_PROMPT = (
    "あなたはチャットボットとして動作するアシスタントです。"
    "簡潔に、チャットに適した長さで日本語で答えてください。"
)


def parse_allowed_tools() -> list[str]:
    raw = os.environ.get("BOT_ALLOWED_TOOLS")
    if raw is None:
        return list(DEFAULT_ALLOWED_TOOLS)
    return [tool.strip() for tool in raw.split(",") if tool.strip()]


class ClaudeAgent(Agent):
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        allowed_tools: list[str] | None = None,
    ):
        self._model = model
        self._system_prompt = system_prompt
        self._allowed_tools = allowed_tools if allowed_tools is not None else parse_allowed_tools()
        self._mcp_options: dict = agent_options()
        if self._mcp_options:
            self._system_prompt += system_prompt_suffix()
            logger.info("MCP enabled: %s", ", ".join(enabled_servers()))
        # conversation_id -> Claude session_id (resumed on each turn)
        self._sessions: dict[str, str] = {}
        # Serialize turns per conversation so resume doesn't race
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def _build_options(self, conversation_id: str) -> ClaudeAgentOptions:
        allowed_tools = list(self._allowed_tools)
        if mcp_allowed := self._mcp_options.get("allowed_tools"):
            allowed_tools.extend(mcp_allowed)

        kwargs: dict = {
            "model": self._model,
            "system_prompt": self._system_prompt,
            "resume": self._sessions.get(conversation_id),
            "tools": self._allowed_tools,
            "allowed_tools": allowed_tools,
            "permission_mode": "dontAsk",
            "setting_sources": [],
        }
        if mcp_servers := self._mcp_options.get("mcp_servers"):
            kwargs["mcp_servers"] = mcp_servers
        return ClaudeAgentOptions(**kwargs)

    async def reply(self, conversation_id: str, prompt: str) -> str:
        async with self._locks[conversation_id]:
            options = self._build_options(conversation_id)
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
                    if message.permission_denials:
                        denied = ", ".join(
                            denial.get("tool_name", "unknown")
                            if isinstance(denial, dict)
                            else getattr(denial, "tool_name", "unknown")
                            for denial in message.permission_denials
                        )
                        return f"ツールの使用が拒否されました: {denied}"
            return "\n".join(parts)
