"""MCP server configurations aggregated from environment."""

from mcp_servers import github

__all__ = ["agent_options", "enabled_servers", "system_prompt_suffix"]


def enabled_servers() -> list[str]:
    servers: list[str] = []
    if github.token():
        servers.append(github.SERVER_NAME)
    return servers


def agent_options() -> dict:
    """Return ClaudeAgentOptions kwargs for all enabled MCP servers."""
    mcp_servers: dict = {}
    allowed_tools: list[str] = []

    if token := github.token():
        opts = github.options(token)
        mcp_servers.update(opts["mcp_servers"])
        allowed_tools.extend(opts["allowed_tools"])

    if not mcp_servers:
        return {}

    return {"mcp_servers": mcp_servers, "allowed_tools": allowed_tools}


def system_prompt_suffix() -> str:
    parts: list[str] = []
    if github.token():
        parts.append(github.system_prompt_suffix())
    return "".join(parts)
