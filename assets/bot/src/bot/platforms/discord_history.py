"""Discord channel message history fetching."""

import logging
import os
import re

import discord

logger = logging.getLogger(__name__)

MENTION_RE = re.compile(r"<@!?\d+>")
MAX_PAGE_SIZE = 100
DEFAULT_HISTORY_LIMIT = 100


def configured_history_limit() -> int:
    return int(os.environ.get("BOT_DISCORD_HISTORY_LIMIT", DEFAULT_HISTORY_LIMIT))


def _message_text(msg: discord.Message) -> str:
    return MENTION_RE.sub("", msg.content).strip()


def _should_include(msg: discord.Message, bot_user_id: int) -> bool:
    if not _message_text(msg):
        return False
    return not (msg.author.bot and msg.author.id != bot_user_id)


def format_message(msg: discord.Message, bot_user_id: int) -> str:
    content = _message_text(msg)
    author = "Bot" if msg.author.id == bot_user_id else msg.author.display_name
    if isinstance(msg.channel, discord.Thread):
        return f"[{msg.channel.name}] {author}: {content}"
    return f"{author}: {content}"


async def fetch_history(
    channel: discord.abc.Messageable,
    *,
    bot_user_id: int,
    before_message_id: int,
    limit: int = DEFAULT_HISTORY_LIMIT,
    query: str | None = None,
) -> list[discord.Message]:
    """Fetch channel messages before *before_message_id*, oldest first."""
    limit = min(max(limit, 0), MAX_PAGE_SIZE)
    if limit <= 0:
        return []

    query_text = (query or "").strip().lower()
    before = discord.Object(id=before_message_id)
    collected: list[discord.Message] = []
    max_scan = MAX_PAGE_SIZE * 10 if query_text else limit

    try:
        async for msg in channel.history(limit=max_scan, before=before):
            if not _should_include(msg, bot_user_id):
                continue
            if query_text and query_text not in msg.content.lower():
                continue
            collected.append(msg)
            if len(collected) >= limit:
                break
    except (discord.Forbidden, discord.HTTPException) as exc:
        logger.warning("discord history fetch failed for channel %s: %s", getattr(channel, "id", channel), exc)
        return []

    collected.reverse()
    return collected


async def _resolve_message_channel(
    message: discord.Message,
    channel_id: int,
) -> discord.abc.Messageable | None:
    if channel_id == message.channel.id:
        return message.channel

    if message.guild is None:
        return None

    channel = message.guild.get_channel(channel_id)
    if channel is not None:
        return channel

    try:
        return await message.guild.fetch_channel(channel_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None


async def fetch_reply_chain(message: discord.Message, *, bot_user_id: int) -> list[discord.Message]:
    """Follow message.reference upward and return the chain, oldest first."""
    chain: list[discord.Message] = []
    reference = message.reference
    resolved = message.reference.resolved if message.reference else None

    while reference and reference.message_id:
        if isinstance(resolved, discord.Message):
            current = resolved
        else:
            channel = await _resolve_message_channel(message, reference.channel_id or message.channel.id)
            if channel is None:
                break
            try:
                current = await channel.fetch_message(reference.message_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                break

        if current.author.bot and current.author.id != bot_user_id:
            break
        chain.append(current)
        reference = current.reference
        resolved = current.reference.resolved if current.reference else None

    chain.reverse()
    return chain


def _dedupe_and_cap(messages: list[discord.Message], limit: int) -> list[discord.Message]:
    merged = sorted({msg.id: msg for msg in messages}.values(), key=lambda msg: msg.created_at)
    if limit > 0 and len(merged) > limit:
        merged = merged[-limit:]
    return merged


def _related_threads(
    channel: discord.TextChannel,
    channel_messages: list[discord.Message],
) -> list[discord.Thread]:
    threads: dict[int, discord.Thread] = {}
    starter_ids = {msg.id for msg in channel_messages}

    for msg in channel_messages:
        if msg.thread is not None:
            threads[msg.thread.id] = msg.thread

    for thread in channel.threads:
        starter = thread.starter_message
        if starter is not None and starter.id in starter_ids:
            threads[thread.id] = thread

    return list(threads.values())


async def _fetch_related_thread_messages(
    channel: discord.TextChannel,
    *,
    channel_messages: list[discord.Message],
    bot_user_id: int,
    before_message_id: int,
    limit: int,
) -> list[discord.Message]:
    threads = _related_threads(channel, channel_messages)
    if not threads:
        return []

    per_thread_limit = max(limit // len(threads), 1)
    collected: list[discord.Message] = []
    for thread in threads:
        collected.extend(
            await fetch_history(
                thread,
                bot_user_id=bot_user_id,
                before_message_id=before_message_id,
                limit=per_thread_limit,
            )
        )
    return collected


async def build_discord_context(
    message: discord.Message,
    *,
    bot_user_id: int,
    history_limit: int | None = None,
) -> str:
    """Build a prompt prefix from channel history, thread history, and the reply chain."""
    limit = history_limit if history_limit is not None else configured_history_limit()
    messages: list[discord.Message] = []

    if isinstance(message.channel, discord.Thread):
        parent = message.channel.parent
        if parent is not None:
            messages.extend(
                await fetch_history(
                    parent,
                    bot_user_id=bot_user_id,
                    before_message_id=message.id,
                    limit=limit,
                )
            )
        messages.extend(
            await fetch_history(
                message.channel,
                bot_user_id=bot_user_id,
                before_message_id=message.id,
                limit=limit,
            )
        )
    else:
        channel_messages = await fetch_history(
            message.channel,
            bot_user_id=bot_user_id,
            before_message_id=message.id,
            limit=limit,
        )
        messages.extend(channel_messages)
        if isinstance(message.channel, discord.TextChannel):
            messages.extend(
                await _fetch_related_thread_messages(
                    message.channel,
                    channel_messages=channel_messages,
                    bot_user_id=bot_user_id,
                    before_message_id=message.id,
                    limit=limit,
                )
            )

    reply_chain = await fetch_reply_chain(message, bot_user_id=bot_user_id)
    if reply_chain:
        messages.extend(reply_chain)

    messages = _dedupe_and_cap(messages, limit)

    lines = [format_message(msg, bot_user_id) for msg in messages if _message_text(msg)]
    if not lines:
        return ""
    return "[Discord上の過去のやりとり]\n" + "\n".join(lines) + "\n\n"
