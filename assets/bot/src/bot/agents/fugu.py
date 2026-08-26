"""Sakana Fugu agent via the OpenAI-compatible Responses API."""

import asyncio
import logging
import os
from collections import defaultdict

from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI, RateLimitError

from bot.agents.base import Agent
from bot.agents.claude import DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "fugu"
DEFAULT_BASE_URL = "https://api.sakana.ai"
SUPPORTED_MODELS = frozenset({"fugu", "fugu-ultra", "fugu-ultra-20260615"})

FUGU_SYSTEM_PROMPT = (
    DEFAULT_SYSTEM_PROMPT.replace(
        "WebSearchやWebFetchを使う際は、ユーザーの質問に答えるのに役立つ情報を探してください。",
        "Web検索を使う際は、ユーザーの質問に答えるのに役立つ情報を探してください。",
    )
    .replace(
        "通常の質問はWebSearch/WebFetchを自分で使い、毎回サブエージェントに任せないでください。",
        "必要なときはWeb検索を使ってください。",
    )
    .replace(
        "5件以上のソース確認など大規模な調査が必要なときだけ、Agentツールのexploreサブエージェントに任せてください。",
        "複数の情報源を確認する必要があるときは、Web検索を繰り返して調査してください。",
    )
    .replace(
        "単純な計算や短い整形だけならquickサブエージェントを使えます。",
        "",
    )
)


def parse_fugu_model() -> str:
    raw = os.environ.get("FUGU_MODEL", DEFAULT_MODEL).strip()
    if raw not in SUPPORTED_MODELS:
        raise ValueError(
            f"unsupported FUGU_MODEL: {raw!r} "
            f"(expected one of: {', '.join(sorted(SUPPORTED_MODELS))})"
        )
    return raw


def parse_fugu_base_url() -> str:
    raw = os.environ.get("FUGU_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    if not raw:
        raw = DEFAULT_BASE_URL
    if not raw.endswith("/v1"):
        raw = f"{raw}/v1"
    return raw


def parse_sakana_api_key() -> str:
    raw = os.environ.get("SAKANA_API_KEY", "").strip()
    if not raw:
        raise ValueError("SAKANA_API_KEY is required for the Fugu backend")
    return raw


def parse_web_search_enabled() -> bool:
    raw = os.environ.get("BOT_FUGU_WEB_SEARCH")
    if raw is None:
        return True
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _format_api_error(exc: Exception) -> str:
    if isinstance(exc, AuthenticationError):
        return "SAKANA_API_KEY が無効です。console.sakana.ai でキーを確認してください。"
    if isinstance(exc, RateLimitError):
        return "Sakana Fugu の利用上限に達しました。しばらく待ってから再度お試しください。"
    if isinstance(exc, APIConnectionError):
        return "Sakana Fugu API (api.sakana.ai) に接続できませんでした。"
    if isinstance(exc, APIStatusError):
        detail = exc.message.strip() if exc.message else f"HTTP {exc.status_code}"
        if exc.status_code == 429:
            return f"Sakana Fugu の利用上限に達しました: {detail}"
        return f"Sakana Fugu API エラー: {detail}"
    return f"エラーが発生しました: {exc}"


class FuguAgent(Agent):
    def __init__(
        self,
        system_prompt: str = FUGU_SYSTEM_PROMPT,
        model: str | None = None,
        web_search: bool | None = None,
    ):
        self._system_prompt = system_prompt
        self._model = model if model is not None else parse_fugu_model()
        self._web_search = web_search if web_search is not None else parse_web_search_enabled()
        self._client = OpenAI(
            api_key=parse_sakana_api_key(),
            base_url=parse_fugu_base_url(),
        )
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def _build_request_kwargs(self, prompt: str) -> dict:
        kwargs: dict = {
            "model": self._model,
            "instructions": self._system_prompt,
            "input": prompt,
        }
        if self._web_search:
            kwargs["tools"] = [{"type": "web_search"}]
        return kwargs

    async def reply(self, conversation_id: str, prompt: str) -> str:
        async with self._locks[conversation_id]:
            kwargs = self._build_request_kwargs(prompt)
            try:
                response = await asyncio.to_thread(self._client.responses.create, **kwargs)
            except Exception as exc:
                error_text = _format_api_error(exc)
                logger.error(
                    "Fugu agent error in conversation %s: %s",
                    conversation_id,
                    error_text,
                    exc_info=exc,
                )
                return error_text

            reply_text = (response.output_text or "").strip()
            if not reply_text:
                logger.warning(
                    "Fugu agent returned empty reply in conversation %s (model=%s)",
                    conversation_id,
                    self._model,
                )
            return reply_text
