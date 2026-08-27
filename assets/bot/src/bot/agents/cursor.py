"""Cursor agent backed by the Cursor SDK."""

import asyncio
import logging
import os
from collections import defaultdict
from pathlib import Path

from cursor_sdk import (
    AgentOptions,
    AsyncClient,
    AuthenticationError,
    CloudAgentOptions,
    CursorAgentError,
    LocalAgentOptions,
    RateLimitError,
)
from cursor_sdk.asyncio import AsyncAgent, AsyncRun

from bot.agents.base import Agent
from bot.agents.prompts import DEFAULT_SYSTEM_PROMPT
from mcp_servers import agent_options, enabled_servers, system_prompt_suffix

logger = logging.getLogger(__name__)

DEFAULT_CWD = Path(__file__).resolve().parents[3] / ".cursor-bot-workspace"
DEFAULT_MODEL = "default"
_SYSTEM_PREAMBLE = "[システム指示]\n"


def parse_cursor_api_key() -> str:
    raw = os.environ.get("CURSOR_API_KEY", "").strip()
    if not raw:
        raise ValueError("CURSOR_API_KEY is required for the Cursor backend")
    return raw


def parse_cursor_model() -> str | None:
    raw = os.environ.get("BOT_MODEL")
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped or None


def parse_cursor_cwd() -> str:
    raw = os.environ.get("BOT_CURSOR_CWD")
    if raw:
        return raw.strip()
    DEFAULT_CWD.mkdir(parents=True, exist_ok=True)
    return str(DEFAULT_CWD)


def _format_api_error(exc: Exception) -> str:
    if isinstance(exc, AuthenticationError):
        return (
            "CURSOR_API_KEY が無効です。"
            "Cursor Dashboard の API Keys でキーを確認してください。"
        )
    if isinstance(exc, RateLimitError):
        return "Cursor の利用上限に達しました。しばらく待ってから再度お試しください。"
    if isinstance(exc, CursorAgentError):
        detail = exc.message.strip() or str(exc)
        lowered = detail.lower()
        if exc.status == 429 or "usage limit" in lowered or "rate limit" in lowered:
            return f"Cursor の利用上限に達しました: {detail}"
        return f"エラーが発生しました: {detail}"
    return f"エラーが発生しました: {exc}"


class CursorAgent(Agent):
    def __init__(
        self,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        model: str | None = None,
        api_key: str | None = None,
    ):
        self._system_prompt = system_prompt
        self._model = model if model is not None else parse_cursor_model()
        self._api_key = api_key if api_key is not None else parse_cursor_api_key()
        self._mcp_options: dict = agent_options()
        if self._mcp_options:
            self._system_prompt += system_prompt_suffix()
            logger.info("MCP enabled: %s", ", ".join(enabled_servers()))
        self._client: AsyncClient | None = None
        self._client_lock = asyncio.Lock()
        self._agents: dict[str, AsyncAgent] = {}
        self._system_sent: dict[str, bool] = defaultdict(bool)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def _ensure_client(self) -> AsyncClient:
        async with self._client_lock:
            if self._client is None:
                self._client = await AsyncClient.launch_bridge(
                    workspace=parse_cursor_cwd(),
                )
            return self._client

    def _build_create_options(self, conversation_id: str) -> AgentOptions:
        mcp_servers = self._mcp_options.get("mcp_servers")
        if self._model is None:
            return AgentOptions(
                api_key=self._api_key,
                name=f"discord-{conversation_id[:32]}",
                model=DEFAULT_MODEL,
                cloud=CloudAgentOptions(),
                mcp_servers=mcp_servers,
            )
        return AgentOptions(
            api_key=self._api_key,
            name=f"discord-{conversation_id[:32]}",
            model=self._model,
            local=LocalAgentOptions(
                cwd=parse_cursor_cwd(),
                setting_sources=[],
            ),
            mcp_servers=mcp_servers,
        )

    async def _get_or_create_agent(self, conversation_id: str) -> AsyncAgent:
        if conversation_id in self._agents:
            return self._agents[conversation_id]
        client = await self._ensure_client()
        agent = await client.agents.create(
            self._build_create_options(conversation_id),
        )
        self._agents[conversation_id] = agent
        return agent

    def _format_prompt(self, conversation_id: str, prompt: str) -> str:
        if self._system_sent[conversation_id]:
            return prompt
        self._system_sent[conversation_id] = True
        return f"{_SYSTEM_PREAMBLE}{self._system_prompt}\n\n{prompt}"

    async def _extract_reply(self, run: AsyncRun) -> str:
        parts: list[str] = []
        async for chunk in run.iter_text():
            parts.append(chunk)
        reply = "".join(parts).strip()
        if reply:
            return reply
        return (await run.text()).strip()

    async def reply(self, conversation_id: str, prompt: str) -> str:
        async with self._locks[conversation_id]:
            agent = await self._get_or_create_agent(conversation_id)
            message = self._format_prompt(conversation_id, prompt)
            try:
                run = await agent.send(message)
                reply_text = await self._extract_reply(run)
                result = await run.wait()
            except Exception as exc:
                error_text = _format_api_error(exc)
                logger.error(
                    "Cursor agent error in conversation %s: %s",
                    conversation_id,
                    error_text,
                    exc_info=exc,
                )
                return error_text

            if result.status == "error":
                detail = result.result.strip() or "unknown error"
                error_text = f"エラーが発生しました: {detail}"
                logger.error(
                    "Cursor agent run failed in conversation %s: %s",
                    conversation_id,
                    error_text,
                )
                return error_text

            if not reply_text:
                logger.warning(
                    "Cursor agent returned empty reply in conversation %s (model=%s)",
                    conversation_id,
                    result.model.id if result.model else self._model or "default",
                )
            return reply_text
