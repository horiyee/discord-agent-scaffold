"""Discord platform adapter: relays mentions/DMs to an Agent."""

import logging
import os
import re

import discord

from bot.agents.base import Agent
from bot.platforms.discord_history import build_discord_context

logger = logging.getLogger(__name__)

MENTION_RE = re.compile(r"<@!?\d+>")
DISCORD_MESSAGE_LIMIT = 2000
DEFAULT_THREAD_NAME = "ボットとの会話"
MAX_THREAD_NAME_LEN = 100


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class DiscordBot(discord.Client):
    def __init__(self, agent: Agent):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self._agent = agent
        self._reply_in_thread = _env_bool("BOT_REPLY_IN_THREAD", True)

    async def on_ready(self) -> None:
        logger.info("logged in as %s", self.user)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        is_dm = message.guild is None
        if not is_dm and self.user not in message.mentions:
            return

        prompt = MENTION_RE.sub("", message.content).strip()
        if not prompt:
            return

        reply_channel = await self._resolve_reply_channel(message)
        conversation_id = str(reply_channel.id)

        history = await build_discord_context(message, bot_user_id=self.user.id)
        user_prompt = self._format_user_prompt(message, prompt)
        agent_prompt = f"{history}{user_prompt}" if history else user_prompt

        try:
            async with reply_channel.typing():
                reply = await self._agent.reply(conversation_id, agent_prompt)
        except Exception:
            logger.exception("agent error in channel %s", reply_channel.id)
            await self._send_chunks(reply_channel, message, "内部エラーが発生しました。")
            return

        if not reply:
            reply = "(応答がありませんでした)"
        await self._send_chunks(reply_channel, message, reply)

    async def _resolve_reply_channel(self, message: discord.Message) -> discord.abc.Messageable:
        if message.guild is None:
            return message.channel

        if isinstance(message.channel, discord.Thread):
            return message.channel

        if message.thread is not None:
            return message.thread

        if not self._reply_in_thread:
            return message.channel

        # TextChannel covers both text and announcement (news) channels in discord.py 2.x.
        if not isinstance(message.channel, discord.TextChannel):
            return message.channel

        thread_name = self._thread_name(message)
        thread = await message.create_thread(
            name=thread_name,
            auto_archive_duration=1440,
        )
        logger.info("created thread %s for mention in channel %s", thread.id, message.channel.id)
        return thread

    def _thread_name(self, message: discord.Message) -> str:
        prompt = MENTION_RE.sub("", message.content).strip()
        if not prompt:
            return DEFAULT_THREAD_NAME
        first_line = prompt.splitlines()[0].strip()
        if len(first_line) <= MAX_THREAD_NAME_LEN:
            return first_line
        return first_line[: MAX_THREAD_NAME_LEN - 1] + "…"

    def _format_user_prompt(self, message: discord.Message, prompt: str) -> str:
        author = message.author.display_name
        return f"[ユーザーのメッセージ]\n{author}: {prompt}"

    def _thread_reply_reference(
        self, thread: discord.Thread, trigger: discord.Message
    ) -> discord.MessageReference:
        # Starter messages live in the parent channel; reference them from the thread
        # using the thread's channel_id (see Discord API message_reference rules).
        return discord.MessageReference(
            message_id=trigger.id,
            channel_id=thread.id,
            guild_id=trigger.guild.id if trigger.guild else None,
            fail_if_not_exists=False,
        )

    async def _send_chunks(
        self,
        reply_channel: discord.abc.Messageable,
        trigger: discord.Message,
        content: str,
    ) -> None:
        in_thread = isinstance(reply_channel, discord.Thread)
        for i in range(0, len(content), DISCORD_MESSAGE_LIMIT):
            chunk = content[i : i + DISCORD_MESSAGE_LIMIT]
            if i == 0:
                if in_thread:
                    await reply_channel.send(
                        chunk,
                        reference=self._thread_reply_reference(reply_channel, trigger),
                        mention_author=False,
                    )
                else:
                    await trigger.reply(chunk, mention_author=False)
            else:
                await reply_channel.send(chunk)
