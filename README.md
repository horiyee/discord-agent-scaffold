# discord-agent-scaffold

[Agent Skill](https://agentskills.io) for scaffolding Discord AI agent bots
(Claude Agent SDK boilerplate with threads, history, web tools, optional GitHub MCP).

Works with Claude (Claude Code / skills-compatible clients) and other agents that
load the Agent Skills open format.

## Layout

```text
discord-agent-scaffold/          # skill directory (name matches SKILL.md)
├── SKILL.md                     # metadata + agent instructions
├── assets/
│   └── bot/                     # thick runnable template
├── references/
│   └── template-overview.md     # on-demand detail
├── README.md
└── LICENSE
```

Per the [Agent Skills spec](https://agentskills.io/specification): `assets/` holds
templates; `references/` is loaded on demand; `scripts/` can be added later.

## Install as a skill

Point your client at this directory (or a clone of it) using that client’s skill
install path. Examples:

- **Claude Code / Agent Skills**: install or symlink into the client’s skills
  directory so the folder name remains `discord-agent-scaffold`
- **Cursor**: add as a project or user skill the same way (directory containing
  `SKILL.md`)

The skill `name` in frontmatter is `discord-agent-scaffold` and **must match**
the parent directory name.

## Use

Ask the agent to scaffold a Discord AI bot (persona, role, destination). It
should follow `SKILL.md`: copy `assets/bot/`, then edit the system prompt and
thread name.

## Run the template bot directly

```sh
cd assets/bot
uv sync
export DISCORD_BOT_TOKEN=...
uv run bot
```

See [`assets/bot/README.md`](assets/bot/README.md).
