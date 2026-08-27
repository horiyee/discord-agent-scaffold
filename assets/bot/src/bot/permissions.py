"""Owner checks for privileged bot capabilities.

Personal bots usually only need Owner vs everyone else. Set
``BOT_OWNER_USER_IDS`` to your Discord snowflake(s). Privileged features
(currently GitHub MCP) are limited to owners when that list is set; leave it
unset to keep those features open to all users.
"""

from __future__ import annotations

import os


def owner_user_ids() -> frozenset[int]:
    """Return configured owner Discord user IDs (empty if unrestricted)."""
    raw = os.environ.get("BOT_OWNER_USER_IDS")
    if raw is None or not raw.strip():
        return frozenset()
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        ids.add(int(part))
    return frozenset(ids)


def is_owner(discord_user_id: int | None) -> bool:
    if discord_user_id is None:
        return False
    owners = owner_user_ids()
    if not owners:
        return False
    return discord_user_id in owners


def can_use_github_mcp(discord_user_id: int | None) -> bool:
    """GitHub MCP is owner-only when owners are configured; otherwise open."""
    owners = owner_user_ids()
    if not owners:
        return True
    return is_owner(discord_user_id)
