"""GitHub MCP server configuration (standard integration)."""

import os

SERVER_NAME = "github"
NPM_PACKAGE = "@modelcontextprotocol/server-github"
MCP_TOKEN_ENV = "GITHUB_PERSONAL_ACCESS_TOKEN"


def name() -> str:
    return SERVER_NAME


def token() -> str | None:
    """Return a GitHub token from the environment, if configured."""
    return os.environ.get(MCP_TOKEN_ENV)


def enabled() -> bool:
    return token() is not None


def agent_options() -> dict:
    """Build agent kwargs for the GitHub MCP server."""
    if not (token_value := token()):
        return {}
    return {
        "mcp_servers": {
            SERVER_NAME: {
                "command": "npx",
                "args": ["-y", NPM_PACKAGE],
                "env": {MCP_TOKEN_ENV: token_value},
            }
        },
        "allowed_tools": [f"mcp__{SERVER_NAME}__*"],
    }


def system_prompt_suffix() -> str:
    return (
        " GitHub MCP が有効です。"
        "Issue や PR の確認、リポジトリ情報の取得など、GitHub 上の操作を依頼できます。"
    )
