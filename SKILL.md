---
name: discord-agent-scaffold
description: >-
  Scaffold a customized Discord AI agent bot from a thick Claude Agent SDK
  boilerplate (mention/DM triggers, thread replies, channel history context,
  WebSearch/WebFetch, optional GitHub MCP). Use when creating a new Discord
  bot, spinning up a Discord AI agent, or customizing a bot persona from this
  template.
license: MIT
compatibility: Requires Python 3.14+, uv, Discord bot token, and Claude Code auth or ANTHROPIC_API_KEY. Optional Node.js/npx for GitHub MCP.
metadata:
  author: horiyee
  version: "0.1"
---

# Scaffold a Discord AI agent bot

Copy the thick bot template from [`assets/bot/`](assets/bot/), then apply
persona/flavor. Do not rewrite the Discord or Claude wiring from scratch.

For design details, see [`references/template-overview.md`](references/template-overview.md).

## When to use

- User wants a new Discord AI / agent bot
- User asks to scaffold from `discord-agent-scaffold`
- User wants a custom persona on top of mention/DM + thread UX

## What `assets/bot` already includes

| Area | Behavior |
| --- | --- |
| Triggers | Guild `@mention` or DM |
| Threads | Mention in a text channel creates a thread and replies inside it |
| Context | Recent history + reply chain; author display name in the prompt |
| Agent | Claude Agent SDK with per-conversation session resume |
| Tools | `WebSearch`, `WebFetch` via `BOT_ALLOWED_TOOLS` |
| MCP | GitHub MCP when `GITHUB_TOKEN` or `GITHUB_PERSONAL_ACCESS_TOKEN` is set |
| Model | Default `claude-opus-4-6` (`BOT_MODEL` overrides) |

## Workflow

### 1. Gather flavor

Collect if missing: bot name, persona/tone, role/domain, default thread name,
destination path. Optional: model; whether to keep web tools / GitHub MCP.

### 2. Copy the template

Copy the entire package (keep it thick):

```text
assets/bot/  →  <destination>/bot/
```

Resolve `assets/bot` relative to this skill root (the directory that contains
this `SKILL.md`).

```sh
cp -R assets/bot <destination>/bot
```

Preserve `pyproject.toml`, `uv.lock`, `.python-version`, `src/bot/**`,
`src/mcp_servers/**`, and the template README.

### 3. Apply flavor

| Location | Change |
| --- | --- |
| `src/bot/agents/claude.py` → `DEFAULT_SYSTEM_PROMPT` | Persona + role |
| `src/bot/platforms/discord.py` → `DEFAULT_THREAD_NAME` | Fallback thread title |
| `README.md` / `pyproject.toml` | Name, purpose, authors |

Leave platform modules alone unless fixing a bug.

### 4. Hand off runbook

1. Discord app: enable **Message Content Intent**
2. Invite with Send Messages, Create Public Threads, Send Messages in Threads, Read Message History
3. `cd bot && uv sync`
4. Export `DISCORD_BOT_TOKEN` (+ Claude auth or `ANTHROPIC_API_KEY`)
5. `uv run bot`
6. `@mention` in a guild channel (expect a thread) or DM

## Anti-patterns

- Building a thinner stub instead of copying `assets/bot`
- Dropping history / MCP / web tools without being asked
- Committing tokens or secrets
