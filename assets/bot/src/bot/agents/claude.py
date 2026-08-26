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


_ASSISTANT_ERROR_MESSAGES = {
    "authentication_failed": (
        "Claude Code にログインしていません。"
        "`claude` でログインするか、ANTHROPIC_API_KEY を設定してください。"
    ),
    "billing_error": "Anthropic の課金設定に問題があります。",
    "rate_limit": (
        "Claude Code の利用上限に達しました。"
        "リセット時刻を確認して、しばらく待ってから再度お試しください。"
    ),
    "invalid_request": "リクエストが無効です。",
    "server_error": "Anthropic 側でサーバーエラーが発生しました。",
}

_USAGE_LIMIT_MARKERS = (
    "session limit",
    "weekly limit",
    "usage limit",
    "rate limit",
    "rate limited",
    "hit your limit",
    "opus limit",
    "sonnet limit",
    "credit balance",
    "limiting requests",
)


def _is_usage_limit_error(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _USAGE_LIMIT_MARKERS)


def _format_result_error(
    message: ResultMessage,
    *,
    assistant_error: str | None = None,
) -> str:
    """Build a user-facing error string from a failed ResultMessage."""
    if message.errors:
        detail = "; ".join(message.errors)
    elif message.result:
        detail = message.result.strip()
    elif message.api_error_status is not None:
        detail = f"HTTP {message.api_error_status}"
    elif assistant_error:
        detail = _ASSISTANT_ERROR_MESSAGES.get(assistant_error, assistant_error)
    elif message.subtype and message.subtype != "success":
        detail = message.subtype
    else:
        detail = "unknown error"

    if assistant_error and detail == message.result:
        translated = _ASSISTANT_ERROR_MESSAGES.get(assistant_error)
        if translated:
            detail = translated

    lowered = detail.lower()
    if message.api_error_status == 429 or _is_usage_limit_error(lowered):
        if message.result and message.result.strip():
            detail = f"Claude Code の利用上限に達しました: {message.result.strip()}"
        else:
            detail = _ASSISTANT_ERROR_MESSAGES["rate_limit"]
    elif assistant_error == "rate_limit":
        detail = _ASSISTANT_ERROR_MESSAGES["rate_limit"]
    elif "not logged in" in lowered or "please run /login" in lowered:
        detail = _ASSISTANT_ERROR_MESSAGES["authentication_failed"]
    elif "invalid api key" in lowered:
        detail = (
            "ANTHROPIC_API_KEY が無効です。"
            "正しい API キーを設定するか、`claude` でログインしてください。"
        )

    return f"エラーが発生しました: {detail}"


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
            assistant_error: str | None = None
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    if message.error:
                        assistant_error = message.error
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            parts.append(block.text)
                elif isinstance(message, ResultMessage):
                    self._sessions[conversation_id] = message.session_id
                    if message.is_error:
                        error_text = _format_result_error(
                            message, assistant_error=assistant_error
                        )
                        logger.error(
                            "Claude agent error in conversation %s: %s",
                            conversation_id,
                            error_text,
                        )
                        return error_text
                    if message.permission_denials:
                        denied = ", ".join(
                            denial.get("tool_name", "unknown")
                            if isinstance(denial, dict)
                            else getattr(denial, "tool_name", "unknown")
                            for denial in message.permission_denials
                        )
                        return f"ツールの使用が拒否されました: {denied}"
            return "\n".join(parts)
