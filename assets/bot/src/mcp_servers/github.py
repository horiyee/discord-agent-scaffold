"""GitHub MCP server configuration."""

import os

SERVER_NAME = "github"
NPM_PACKAGE = "@modelcontextprotocol/server-github"


def token() -> str | None:
    """Return a GitHub token from the environment, if configured."""
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")


def options(token_value: str) -> dict:
    """Build ClaudeAgentOptions kwargs for the GitHub MCP server."""
    return {
        "mcp_servers": {
            SERVER_NAME: {
                "command": "npx",
                "args": ["-y", NPM_PACKAGE],
                "env": {"GITHUB_TOKEN": token_value},
            }
        },
        "allowed_tools": [f"mcp__{SERVER_NAME}__*"],
    }


def system_prompt_suffix() -> str:
    return (
        " GitHub MCP が有効です。"
        "Issue や PR の確認、リポジトリ情報の取得など、GitHub 上の操作を依頼できます。"
    )
