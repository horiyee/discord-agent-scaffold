# Template overview

`assets/bot` is a runnable Discord + Claude Agent SDK package.

## Layout

```text
assets/bot/
├── pyproject.toml
├── uv.lock
├── README.md
└── src/
    ├── bot/
    │   ├── __init__.py          # entry: DISCORD_BOT_TOKEN, BOT_AGENT
    │   ├── agents/
    │   │   ├── base.py          # Agent ABC
    │   │   ├── claude.py        # Claude Agent SDK + tools + MCP hooks
    │   │   └── __init__.py      # create_agent / BOT_MODEL
    │   └── platforms/
    │       ├── discord.py       # mention/DM, threads, chunking
    │       └── discord_history.py
    └── mcp_servers/
        ├── __init__.py
        └── github.py            # optional GitHub MCP
```

## Flavor vs core

| Customize (flavor) | Keep (core) |
| --- | --- |
| `DEFAULT_SYSTEM_PROMPT` in `agents/claude.py` | Session resume, locks, tool/MCP option building |
| `DEFAULT_THREAD_NAME` in `platforms/discord.py` | Thread create/reply reference rules, history fetch |
| Bot README intro / `pyproject` metadata | `mcp_servers` wiring |

## Env vars (see also `assets/bot/README.md`)

- Required: `DISCORD_BOT_TOKEN`
- Optional: `BOT_MODEL`, `BOT_ALLOWED_TOOLS`, `BOT_DISCORD_HISTORY_LIMIT`,
  `BOT_REPLY_IN_THREAD`, `GITHUB_TOKEN` / `GITHUB_PERSONAL_ACCESS_TOKEN`
