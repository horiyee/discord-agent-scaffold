# bot

Homelab 上で動く、Claude と対話できるチャットボット。

- `bot.agents` — LLM バックエンドの抽象化(現在: Claude / 将来: Gemini など)
- `bot.platforms` — チャットプラットフォーム(現在: Discord / 将来: Slack など)

Claude バックエンドは [Claude Agent SDK](https://pypi.org/project/claude-agent-sdk/) を使い、
チャンネルごとにセッションを resume して会話を継続します。

## 必要なもの

- ホストで Claude Code の認証が済んでいること(`claude` でログイン済み、または `ANTHROPIC_API_KEY`)
- Discord Bot Token(Developer Portal で **Message Content Intent** を有効にすること)

## 起動

```sh
export DISCORD_BOT_TOKEN=...
uv run bot
```

サーバーではボットへのメンション、DM ではそのまま話しかけると応答します。

## 環境変数

| 変数 | 必須 | 説明 |
| --- | --- | --- |
| `DISCORD_BOT_TOKEN` | ✅ | Discord ボットのトークン |
| `BOT_AGENT` | — | エージェントバックエンド(デフォルト: `claude`) |
| `BOT_MODEL` | — | 使用する Claude モデル(デフォルト: `claude-opus-4-6`) |
| `BOT_ALLOWED_TOOLS` | — | 利用可能なツール(カンマ区切り。デフォルト: `WebSearch,WebFetch`) |

Web 検索・取得にはネットワーク接続と Anthropic API の認証が必要です。`WebSearch` は追加料金が発生する場合があります。
