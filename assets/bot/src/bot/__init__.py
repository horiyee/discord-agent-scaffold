import logging
import os

from bot.agents import AgentRouter
from bot.platforms.discord import DiscordBot


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    agent = AgentRouter()
    bot = DiscordBot(agent)
    bot.run(os.environ["DISCORD_BOT_TOKEN"])
