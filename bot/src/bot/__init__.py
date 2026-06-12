import logging
import os

from bot.agents import create_agent
from bot.platforms.discord import DiscordBot


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    agent = create_agent(os.environ.get("BOT_AGENT", "claude"))
    bot = DiscordBot(agent)
    bot.run(os.environ["DISCORD_BOT_TOKEN"])
