"""Discord platform adapter: relays mentions/DMs to an Agent."""

import logging
import re

import discord

from bot.agents.base import Agent

logger = logging.getLogger(__name__)

MENTION_RE = re.compile(r"<@!?\d+>")
DISCORD_MESSAGE_LIMIT = 2000


class DiscordBot(discord.Client):
    def __init__(self, agent: Agent):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self._agent = agent

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

        agent_prompt = self._format_user_prompt(message, prompt)

        try:
            async with message.channel.typing():
                reply = await self._agent.reply(str(message.channel.id), agent_prompt)
        except Exception:
            logger.exception("agent error in channel %s", message.channel.id)
            await message.reply("内部エラーが発生しました。", mention_author=False)
            return

        if not reply:
            reply = "(応答がありませんでした)"
        for i in range(0, len(reply), DISCORD_MESSAGE_LIMIT):
            await message.reply(reply[i : i + DISCORD_MESSAGE_LIMIT], mention_author=False)

    def _format_user_prompt(self, message: discord.Message, prompt: str) -> str:
        author = message.author.display_name
        return f"[ユーザーのメッセージ]\n{author}: {prompt}"
