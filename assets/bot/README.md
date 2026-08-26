# bot

Homelab 上で動く、Claude と対話できるチャットボット。

- `bot.agents` — LLM バックエンドの抽象化(現在: Claude / 将来: Gemini など)
- `bot.platforms` — チャットプラットフォーム(現在: Discord / 将来: Slack など)
- `mcp_servers` — Claude Agent SDK 向け MCP サーバー設定(`src/mcp_servers`)

Claude バックエンドは [Claude Agent SDK](https://pypi.org/project/claude-agent-sdk/) を使い、
チャンネルごとにセッションを resume して会話を継続します。
メインエージェントのモデルは Claude Code のアカウント設定に従います（モデル名の環境変数指定は不要）。
大規模な Web 調査や軽量タスクは、必要なときだけ Sonnet / Haiku のサブエージェントに委譲できます。

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
export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_...
uv run bot
```

サーバーでは初回はボットへのメンションが必要です。スレッドができたあとは、スレッド内ではメンションなしでも応答します。DM ではそのまま話しかけると応答します。
複数人が同じチャンネルやスレッドで話す場合に備え、発言者の表示名をプロンプトに含めます。

## GitHub 連携

`GITHUB_PERSONAL_ACCESS_TOKEN` を設定すると、`mcp_servers` が
[GitHub MCP サーバー](https://github.com/modelcontextprotocol/servers/tree/main/src/github) の設定を渡し、
Discord から Issue や PR の確認などができます。

トークンは必要なスコープだけ付与してください(読み取り中心なら `repo` や fine-grained token の Read 権限)。
MCP サーバーは `npx @modelcontextprotocol/server-github` で起動するため、ホストに Node.js が必要です。

応答前に Discord 上の直近メッセージ（デフォルト 100 件）を `fetch_history` で取得し、エージェントへのプロンプトに含めます。リプライチェーンもコンテキストに含めます。

スレッド内でメンションされた場合は、親チャンネルの履歴とスレッド内の履歴を時系列でマージして参照します。テキストチャンネルでメンションされた場合は、取得したチャンネル履歴に紐づくスレッド（メッセージに付いたスレッドや、アクティブなスレッドの開始メッセージが履歴内にあるもの）の内容も含めます。スレッド由来のメッセージには `[スレッド名]` プレフィックスが付きます。

### サーバーでの挙動

- **テキストチャンネルでのメンション** — そのメッセージからスレッドを作成し、メンション投稿へのリプライとしてスレッド内に返信します（既にスレッドが付いている場合はそこで継続）
- **スレッド内のメッセージ** — メンションなしでも応答します（初回のメンションでスレッドができたあとの会話用）
- **スレッド内でのメンション** — 上記と同様にスレッド内で返信します

Developer Portal で **Create Public Threads** と **Send Messages in Threads** 権限も付与してください。

## 環境変数

| 変数 | 必須 | 説明 |
| --- | --- | --- |
| `DISCORD_BOT_TOKEN` | ✅ | Discord ボットのトークン |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | — | GitHub Personal Access Token。設定すると GitHub MCP が有効になる |
| `BOT_AGENT` | — | エージェントバックエンド(デフォルト: `claude`) |
| `BOT_ALLOWED_TOOLS` | — | 利用可能なツール(カンマ区切り。デフォルト: `WebSearch,WebFetch,Agent`) |
| `BOT_MAX_TURNS` | — | 1 回の応答あたりの最大ターン数(デフォルト: `12`) |
| `BOT_DISCORD_HISTORY_LIMIT` | — | 参照する Discord 履歴の件数(デフォルト: `100`、`0` で無効) |
| `BOT_REPLY_IN_THREAD` | — | チャンネルでのメンション時にスレッドを作成するか(デフォルト: `true`) |

Web 検索・取得にはネットワーク接続と Anthropic API の認証が必要です。`WebSearch` は追加料金が発生する場合があります。
