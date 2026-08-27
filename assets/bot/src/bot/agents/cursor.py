"""Cursor agent backed by the Cursor SDK."""

import asyncio
import logging
import os
import secrets
from collections import defaultdict
from pathlib import Path

import cursor_sdk._store_callback as _store_callback
import cursor_sdk._tool_callback as _tool_callback
from cursor_sdk import (
    AgentOptions,
    AsyncClient,
    AuthenticationError,
    CloudAgentOptions,
    CursorAgentError,
    LocalAgentOptions,
    NetworkError,
    RateLimitError,
    RunResult,
)
from cursor_sdk.asyncio import AsyncAgent, AsyncRun

from bot.agents.base import Agent
from bot.agents.prompts import DEFAULT_SYSTEM_PROMPT
from bot.mcp import agent_options, enabled_servers, system_prompt_suffix

logger = logging.getLogger(__name__)

DEFAULT_CWD = Path(__file__).resolve().parents[3] / ".cursor-bot-workspace"
DEFAULT_MODEL = "default"
_SYSTEM_PREAMBLE = "[システム指示]\n"
_BRIDGE_TOKEN_WORKAROUND_APPLIED = False


def _apply_bridge_token_workaround() -> None:
    """Avoid cursor-sdk bridge CLI failures when auth tokens start with '-'."""
    global _BRIDGE_TOKEN_WORKAROUND_APPLIED
    if _BRIDGE_TOKEN_WORKAROUND_APPLIED:
        return

    def _safe_auth_token() -> str:
        token = secrets.token_urlsafe(32)
        while token.startswith("-"):
            token = secrets.token_urlsafe(32)
        return token

    _tool_callback._new_auth_token = _safe_auth_token
    _store_callback._new_auth_token = _safe_auth_token
    _BRIDGE_TOKEN_WORKAROUND_APPLIED = True


def _is_bridge_transport_error(exc: Exception) -> bool:
    if isinstance(exc, NetworkError) and exc.is_retryable:
        return True
    lowered = str(exc).lower()
    return "bridge request failed" in lowered and (
        "remoteprotocolerror" in lowered
        or "incomplete chunked" in lowered
        or "peer closed connection" in lowered
    )


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


def _hints_from_stream_message(message: object) -> list[str]:
    """Collect user-facing error hints from one SDK stream message."""
    msg_type = getattr(message, "type", "")
    if msg_type == "status":
        status = str(getattr(message, "status", "")).lower()
        text = str(getattr(message, "message", "")).strip()
        if status in {"error", "failed", "cancelled", "expired"} and text:
            return [text]
        if text and status not in {"", "running", "finished"}:
            return [text]
        return []
    if msg_type == "tool_call" and str(getattr(message, "status", "")).lower() == "error":
        name = str(getattr(message, "name", "tool"))
        result = getattr(message, "result", None)
        if result:
            return [f"{name}: {result}"]
        return [f"{name} failed"]
    return []


def _format_run_error(result: RunResult, hints: list[str]) -> str:
    """Build a user-facing error string from a failed run."""
    detail = result.result.strip()
    if not detail and hints:
        detail = "; ".join(hints)
    if not detail:
        if result.status in {"cancelled", "expired"}:
            detail = result.status
        elif result.id:
            detail = (
                f"原因を特定できませんでした (run_id={result.id})。"
                "サーバーログまたは Cursor Dashboard の Usage を確認してください。"
            )
        else:
            detail = "unknown error"

    lowered = detail.lower()
    if "usage limit" in lowered or "rate limit" in lowered:
        return f"Cursor の利用上限に達しました: {detail}"
    return f"エラーが発生しました: {detail}"


def _format_api_error(exc: Exception) -> str:
    if isinstance(exc, AuthenticationError):
        return (
            "CURSOR_API_KEY が無効です。"
            "Cursor Dashboard の API Keys でキーを確認してください。"
        )
    if isinstance(exc, RateLimitError):
        return "Cursor の利用上限に達しました。しばらく待ってから再度お試しください。"
    if isinstance(exc, NetworkError) or _is_bridge_transport_error(exc):
        detail = exc.message.strip() if isinstance(exc, CursorAgentError) else str(exc)
        return (
            "Cursor SDK の bridge との通信が途中で切れました。"
            "bot の再起動、またはしばらく待ってから再度お試しください。"
            f" ({detail})"
        )
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
                _apply_bridge_token_workaround()
                self._client = await AsyncClient.launch_bridge(
                    workspace=parse_cursor_cwd(),
                )
            return self._client

    async def _reset_bridge(self) -> None:
        async with self._client_lock:
            if self._client is not None:
                try:
                    await self._client.aclose()
                except Exception:
                    logger.exception("failed to close cursor bridge client")
                self._client = None
            self._agents.clear()
            self._system_sent.clear()

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

    async def _collect_run_output(self, run: AsyncRun) -> tuple[str, list[str]]:
        parts: list[str] = []
        hints: list[str] = []
        async for message in run.stream():
            msg_type = getattr(message, "type", "")
            if msg_type == "assistant":
                content = getattr(getattr(message, "message", None), "content", ())
                for block in content:
                    text = getattr(block, "text", "")
                    if text:
                        parts.append(text)
            else:
                hints.extend(_hints_from_stream_message(message))
        reply = "".join(parts).strip()
        if not reply:
            reply = (await run.text()).strip()
        return reply, hints

    async def reply(self, conversation_id: str, prompt: str) -> str:
        async with self._locks[conversation_id]:
            message = self._format_prompt(conversation_id, prompt)
            for attempt in range(2):
                agent = await self._get_or_create_agent(conversation_id)
                try:
                    run = await agent.send(message)
                    reply_text, stream_hints = await self._collect_run_output(run)
                    result = await run.wait()
                except Exception as exc:
                    if attempt == 0 and _is_bridge_transport_error(exc):
                        logger.warning(
                            "Cursor bridge transport error in conversation %s; "
                            "resetting bridge and retrying once",
                            conversation_id,
                            exc_info=exc,
                        )
                        await self._reset_bridge()
                        message = self._format_prompt(conversation_id, prompt)
                        continue
                    error_text = _format_api_error(exc)
                    logger.error(
                        "Cursor agent error in conversation %s: %s",
                        conversation_id,
                        error_text,
                        exc_info=exc,
                    )
                    return error_text

                if result.status == "error":
                    error_text = _format_run_error(result, stream_hints)
                    logger.error(
                        "Cursor agent run failed in conversation %s "
                        "(run_id=%s, model=%s, stream_hints=%s): %s",
                        conversation_id,
                        result.id,
                        result.model.id if result.model else self._model or "default",
                        stream_hints or None,
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

            return (
                "Cursor SDK の bridge との通信が途中で切れました。"
                "bot の再起動、またはしばらく待ってから再度お試しください。"
            )
