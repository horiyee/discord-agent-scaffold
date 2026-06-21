# bot

Homelab 上で動く、Claude と対話できるチャットボット。

- `bot.agents` — LLM バックエンドの抽象化(現在: Claude / 将来: Gemini など)
- `bot.platforms` — チャットプラットフォーム(現在: Discord / 将来: Slack など)
- `mcp_servers` — Claude Agent SDK 向け MCP サーバー設定(`src/mcp_servers`)

Claude バックエンドは [Claude Agent SDK](https://pypi.org/project/claude-agent-sdk/) を使い、
チャンネルごとにセッションを resume して会話を継続します。

## 必要なもの

- ホストで Claude Code の認証が済んでいること(`claude` でログイン済み、または `ANTHROPIC_API_KEY`)
- Discord Bot Token(Developer Portal で **Message Content Intent** を有効にすること)
- GitHub 連携を使う場合: [Personal Access Token](https://github.com/settings/tokens) と Node.js(`npx` が使えること)

## 起動

```sh
cd bot
uv sync
export DISCORD_BOT_TOKEN=...
# 任意: GitHub 連携を有効にする
export GITHUB_TOKEN=ghp_...
uv run bot
```

サーバーではボットへのメンション、DM ではそのまま話しかけると応答します。
複数人が同じチャンネルやスレッドで話す場合に備え、発言者の表示名をプロンプトに含めます。

## GitHub 連携

`GITHUB_TOKEN`(または `GITHUB_PERSONAL_ACCESS_TOKEN`) を設定すると、`mcp_servers` が
[GitHub MCP サーバー](https://github.com/modelcontextprotocol/servers/tree/main/src/github) の設定を渡し、
Discord から Issue や PR の確認などができます。

トークンは必要なスコープだけ付与してください(読み取り中心なら `repo` や fine-grained token の Read 権限)。
MCP サーバーは `npx @modelcontextprotocol/server-github` で起動するため、ホストに Node.js が必要です。

応答前に Discord 上の直近メッセージ（デフォルト 100 件）を `fetch_history` で取得し、エージェントへのプロンプトに含めます。リプライチェーンもコンテキストに含めます。

## 環境変数

| 変数 | 必須 | 説明 |
| --- | --- | --- |
| `DISCORD_BOT_TOKEN` | ✅ | Discord ボットのトークン |
| `GITHUB_TOKEN` | — | GitHub Personal Access Token。設定すると GitHub MCP が有効になる |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | — | `GITHUB_TOKEN` の別名 |
| `BOT_AGENT` | — | エージェントバックエンド(デフォルト: `claude`) |
| `BOT_MODEL` | — | 使用する Claude モデル(デフォルト: `claude-opus-4-6`) |
| `BOT_ALLOWED_TOOLS` | — | 利用可能なツール(カンマ区切り。デフォルト: `WebSearch,WebFetch`) |
| `BOT_DISCORD_HISTORY_LIMIT` | — | 参照する Discord 履歴の件数(デフォルト: `100`、`0` で無効) |

Web 検索・取得にはネットワーク接続と Anthropic API の認証が必要です。`WebSearch` は追加料金が発生する場合があります。
