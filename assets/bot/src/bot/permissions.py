"""Access checks for optional privileged capabilities."""

from __future__ import annotations

import os


def github_mcp_allowed_user_ids() -> frozenset[int] | None:
    """Return Discord user IDs allowed to use GitHub MCP, or None if unrestricted.

    Set ``BOT_GITHUB_MCP_USER_IDS`` to a comma-separated list of snowflakes to
    restrict access. Leave unset (or empty) to allow any user when a token is
    configured.
    """
    raw = os.environ.get("BOT_GITHUB_MCP_USER_IDS")
    if raw is None or not raw.strip():
        return None
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        ids.add(int(part))
    return frozenset(ids)


def can_use_github_mcp(discord_user_id: int | None) -> bool:
    allowed = github_mcp_allowed_user_ids()
    if allowed is None:
        return True
    if discord_user_id is None:
        return False
    return discord_user_id in allowed
