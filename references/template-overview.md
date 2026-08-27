# テンプレート概要

`assets/bot` は実行可能な Discord + Claude Agent SDK パッケージ。

## 構成

```text
assets/bot/
├── pyproject.toml
├── uv.lock
├── README.md
└── src/
    ├── bot/
    │   ├── __init__.py          # 入口: DISCORD_BOT_TOKEN → AgentRouter
    │   ├── model_selection.py   # /model コマンド・永続化
    │   ├── permissions.py       # Owner（特権機能の任意制限）
    │   ├── agents/
    │   │   ├── base.py          # Agent ABC
    │   │   ├── prompts.py       # 共有システムプロンプト（味付け）
    │   │   ├── claude.py        # Claude Agent SDK + ツール + サブエージェント + MCP
    │   │   ├── cursor.py        # Cursor SDK
    │   │   ├── fugu.py          # Sakana Fugu（OpenAI Responses API）
    │   │   ├── factory.py       # create_agent（claude / cursor / fugu）
    │   │   ├── router.py        # AgentRouter（会話ごとのバックエンド選択）
    │   │   └── __init__.py
    │   └── platforms/
    │       ├── discord.py       # メンション/DM、スレッド、/model、分割送信
    │       └── discord_history.py
    └── mcp_servers/
        ├── __init__.py
        └── github.py            # 任意の GitHub MCP
```

## 味付け vs コア

| カスタム（味付け） | 触らない（コア） |
| --- | --- |
| `agents/prompts.py` の `DEFAULT_SYSTEM_PROMPT` | セッション resume、ロック、ツール/MCP 組み立て |
| `platforms/discord.py` の `DEFAULT_THREAD_NAME` | スレ作成・reply reference、履歴取得、`/model` |
| bot README の説明 / `pyproject` のメタデータ | `mcp_servers` の配線、`model_selection` / `AgentRouter` |

## 環境変数（詳細は `assets/bot/README.md`）

- 必須: `DISCORD_BOT_TOKEN`
- 任意: `BOT_ALLOWED_TOOLS`、`BOT_MAX_TURNS`、`BOT_DISCORD_HISTORY_LIMIT`、
  `BOT_REPLY_IN_THREAD`、`GITHUB_PERSONAL_ACCESS_TOKEN`、`BOT_OWNER_USER_IDS`、
  `CURSOR_API_KEY` / `BOT_CURSOR_CWD`（Cursor 時）、
  `SAKANA_API_KEY` / `FUGU_BASE_URL` / `BOT_FUGU_WEB_SEARCH`（Fugu 時）、
  `BOT_MODEL_SWITCHING` / `BOT_MODEL_STATE_FILE`（`/model`）
