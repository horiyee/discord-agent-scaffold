"""MCP server configurations bundled with the bot."""

from bot.mcp import github

__all__ = ["agent_options", "enabled_servers", "system_prompt_suffix"]


def enabled_servers() -> list[str]:
    servers: list[str] = []
    if github.enabled():
        servers.append(github.name())
    return servers


def agent_options() -> dict:
    """Return MCP server kwargs for all enabled providers."""
    mcp_servers: dict = {}
    allowed_tools: list[str] = []

    if github.enabled():
        opts = github.agent_options()
        mcp_servers.update(opts.get("mcp_servers", {}))
        allowed_tools.extend(opts.get("allowed_tools", []))

    if not mcp_servers:
        return {}

    return {"mcp_servers": mcp_servers, "allowed_tools": allowed_tools}


def system_prompt_suffix() -> str:
    parts: list[str] = []
    if github.enabled():
        parts.append(github.system_prompt_suffix())
    return "".join(parts)
