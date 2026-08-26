"""Discord user permission checks."""

from __future__ import annotations

import os

# Default matches Homelab; override with BOT_ADMIN_USER_IDS (comma-separated).
DEFAULT_ADMIN_USER_IDS = (694443538204721185,)


def admin_user_ids() -> frozenset[int]:
    raw = os.environ.get("BOT_ADMIN_USER_IDS")
    if raw is None:
        return frozenset(DEFAULT_ADMIN_USER_IDS)
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        ids.add(int(part))
    return frozenset(ids)


def is_admin(discord_user_id: int | None) -> bool:
    if discord_user_id is None:
        return False
    return discord_user_id in admin_user_ids()


def can_use_github_mcp(discord_user_id: int | None) -> bool:
    return is_admin(discord_user_id)
