"""MCP server configurations aggregated from environment."""

from bot.permissions import can_use_github_mcp
from mcp_servers import github

__all__ = ["agent_options", "enabled_servers", "system_prompt_suffix"]


def enabled_servers(*, discord_user_id: int | None = None) -> list[str]:
    if not can_use_github_mcp(discord_user_id):
        return []
    servers: list[str] = []
    if github.token():
        servers.append(github.SERVER_NAME)
    return servers


def agent_options(*, discord_user_id: int | None = None) -> dict:
    """Return MCP server kwargs for all enabled backends (Claude / Cursor)."""
    if not can_use_github_mcp(discord_user_id):
        return {}

    mcp_servers: dict = {}
    allowed_tools: list[str] = []

    if token := github.token():
        opts = github.options(token)
        mcp_servers.update(opts["mcp_servers"])
        allowed_tools.extend(opts["allowed_tools"])

    if not mcp_servers:
        return {}

    return {"mcp_servers": mcp_servers, "allowed_tools": allowed_tools}


def system_prompt_suffix(*, discord_user_id: int | None = None) -> str:
    if not can_use_github_mcp(discord_user_id):
        return ""
    parts: list[str] = []
    if github.token():
        parts.append(github.system_prompt_suffix())
    return "".join(parts)
