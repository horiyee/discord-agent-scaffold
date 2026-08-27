"""Claude agent backed by the Claude Agent SDK (Claude Code runtime)."""

import asyncio
import logging
import os
from collections import defaultdict

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from bot.agents.base import Agent
from bot.agents.prompts import DEFAULT_SYSTEM_PROMPT
from mcp_servers import agent_options, enabled_servers, system_prompt_suffix

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_TOOLS = ("WebSearch", "WebFetch", "Agent")
DEFAULT_MAX_TURNS = 12
DEFAULT_SUBAGENT_MAX_TURNS = 8

_SUBAGENT_FINAL_REPLY_INSTRUCTION = (
    "作業が終わったら、必ず最後にユーザー向けの要約を日本語のプレーンテキストで書いて終えてください。"
    "ツール呼び出しだけで終わらせないでください。"
)

DEFAULT_SUBAGENTS = {
    "explore": AgentDefinition(
        description=(
            "大規模なWeb調査専用。5件以上のソース確認など、"
            "メインエージェントだけでは手間がかかる調査にだけ使う。"
        ),
        prompt=(
            "あなたは情報収集に特化したサブエージェントです。"
            "WebSearchとWebFetchを使い、必要な事実を集めてください。"
            "一次ソースを優先し、結果は簡潔にまとめて返してください。"
            + _SUBAGENT_FINAL_REPLY_INSTRUCTION
        ),
        tools=["WebSearch", "WebFetch"],
        model="sonnet",
        maxTurns=DEFAULT_SUBAGENT_MAX_TURNS,
    ),
    "quick": AgentDefinition(
        description=(
            "簡単な計算、短い要約、フォーマット変換など軽量な作業。"
            "複雑な調査や深い判断は向かない。"
        ),
        prompt=(
            "あなたは軽量タスク向けのサブエージェントです。"
            "与えられた作業を手早く正確にこなし、結果だけを返してください。"
            + _SUBAGENT_FINAL_REPLY_INSTRUCTION
        ),
        tools=["WebSearch", "WebFetch"],
        model="haiku",
        maxTurns=5,
    ),
}


def parse_allowed_tools() -> list[str]:
    raw = os.environ.get("BOT_ALLOWED_TOOLS")
    if raw is None:
        return list(DEFAULT_ALLOWED_TOOLS)
    return [tool.strip() for tool in raw.split(",") if tool.strip()]


def parse_max_turns() -> int:
    raw = os.environ.get("BOT_MAX_TURNS")
    if raw is None:
        return DEFAULT_MAX_TURNS
    return max(1, int(raw))


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


def _compose_reply(parts: list[str], final_result: str | None) -> str:
    text = "\n".join(parts).strip()
    if not text and final_result:
        text = final_result.strip()
    return text


class ClaudeAgent(Agent):
    def __init__(
        self,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        allowed_tools: list[str] | None = None,
        max_turns: int | None = None,
    ):
        self._system_prompt = system_prompt
        self._allowed_tools = allowed_tools if allowed_tools is not None else parse_allowed_tools()
        self._max_turns = max_turns if max_turns is not None else parse_max_turns()
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
        if "Agent" not in allowed_tools:
            allowed_tools.append("Agent")
        if mcp_allowed := self._mcp_options.get("allowed_tools"):
            allowed_tools.extend(mcp_allowed)

        kwargs: dict = {
            "system_prompt": self._system_prompt,
            "resume": self._sessions.get(conversation_id),
            "tools": allowed_tools,
            "allowed_tools": allowed_tools,
            "agents": DEFAULT_SUBAGENTS,
            "max_turns": self._max_turns,
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
            final_result: str | None = None
            result_message: ResultMessage | None = None
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    if message.error:
                        assistant_error = message.error
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            parts.append(block.text)
                elif isinstance(message, ResultMessage):
                    result_message = message
                    self._sessions[conversation_id] = message.session_id
                    if message.result:
                        final_result = message.result.strip()
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

            reply_text = _compose_reply(parts, final_result)
            if not reply_text and result_message is not None:
                logger.warning(
                    "Claude agent returned empty reply in conversation %s "
                    "(turns=%s, cost=%s, usage=%s)",
                    conversation_id,
                    result_message.num_turns,
                    result_message.total_cost_usd,
                    result_message.usage,
                )
            return reply_text
