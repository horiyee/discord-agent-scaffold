# bot

LLM と対話できる Discord チャットボットのテンプレート。

- `bot.agents` — LLM バックエンドの抽象化(現在: Claude / Cursor / Sakana Fugu)
- `bot.platforms` — チャットプラットフォーム(現在: Discord / 将来: Slack など)
- `mcp_servers` — MCP サーバー設定(`src/mcp_servers`)。Claude / Cursor バックエンドで利用

## バックエンド

起動後は Discord 上の `/model` でバックエンドを切り替えます（後述）。
必要な API キー（`CURSOR_API_KEY` / `SAKANA_API_KEY` など）をあらかじめ設定しておいてください。

### Claude（初回の既定）

Claude バックエンドは [Claude Agent SDK](https://pypi.org/project/claude-agent-sdk/) を使い、
チャンネルごとにセッションを resume して会話を継続します。
メインエージェントのモデルは Claude Code のアカウント設定に従います。
大規模な Web 調査や軽量タスクは、必要なときだけ Sonnet / Haiku のサブエージェントに委譲できます。

Discord で `@bot /model claude` と送ると切り替えられます。

### Sakana Fugu

[Sakana Fugu](https://sakana.ai/fugu/) は OpenAI 互換 API で利用できるマルチエージェントモデルです。
Web 検索は Fugu 組み込みの `web_search` ツールを使います（`BOT_FUGU_WEB_SEARCH=false` で無効化可能）。

API キーは [console.sakana.ai](https://console.sakana.ai/) で作成し、`SAKANA_API_KEY` に設定してください。
Discord で `@bot /model fugu` や `@bot /model fugu-ultra` と送ると切り替えられます。

### Cursor

[Cursor SDK](https://cursor.com/docs/sdk/python) を使い、Cursor Pro などのサブスク枠内でモデルを利用します。

API キーは [Cursor Dashboard → API Keys](https://cursor.com/dashboard) で作成し、`CURSOR_API_KEY` に設定してください。
Discord で `@bot /model cursor`（Auto）や `@bot /model cursor-composer` と送ると切り替えられます。
SDK の利用量は IDE / Cloud Agents と同じ月次枠から消費され、Usage ダッシュボードの **SDK** タグで確認できます。

## 必要なもの

- **Claude 利用時**: ホストで Claude Code の認証が済んでいること(`claude` でログイン済み、または `ANTHROPIC_API_KEY`)
- **Cursor 利用時**: `CURSOR_API_KEY`（Cursor Dashboard で作成）
- **Fugu 利用時**: `SAKANA_API_KEY`（console.sakana.ai で作成）
- Discord Bot Token(Developer Portal で **Message Content Intent** を有効にすること)
- GitHub 連携を使う場合（Claude / Cursor）: [Personal Access Token](https://github.com/settings/tokens) と Node.js(`npx` が使えること)

## 起動

```sh
cd bot
uv sync
export DISCORD_BOT_TOKEN=...
# 任意: Cursor / Fugu を使う場合
# export CURSOR_API_KEY=...
# export SAKANA_API_KEY=...
# 任意: GitHub 連携を有効にする
export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_...
uv run bot
```

起動後、Discord で `@bot /model list` と `@bot /model cursor` などを実行してモデルを選びます。
初回は Claude が既定です（`/model` で一度選べば `.bot-model-state.json` に保存され、以降は再起動後も維持されます）。

サーバーでは初回はボットへのメンションが必要です。スレッドができたあとは、スレッド内ではメンションなしでも応答します。DM ではそのまま話しかけると応答します。
複数人が同じチャンネルやスレッドで話す場合に備え、発言者の表示名をプロンプトに含めます。

## GitHub 連携

`GITHUB_PERSONAL_ACCESS_TOKEN` を設定すると、`mcp_servers` が
[GitHub MCP サーバー](https://github.com/modelcontextprotocol/servers/tree/main/src/github) の設定を渡し、
Discord から Issue や PR の確認などができます。

既定ではトークンを設定したユーザーなら誰でも GitHub MCP を使えます。
特定の Discord ユーザーだけに制限したい場合は `BOT_GITHUB_MCP_USER_IDS`（カンマ区切りのユーザー ID）を設定してください。

トークンは必要なスコープだけ付与してください(読み取り中心なら `repo` や fine-grained token の Read 権限)。
MCP サーバーは `npx @modelcontextprotocol/server-github` で起動するため、ホストに Node.js が必要です。

応答前に Discord 上の直近メッセージ（デフォルト 100 件）を `fetch_history` で取得し、エージェントへのプロンプトに含めます。リプライチェーンもコンテキストに含めます。

スレッド内でメンションされた場合は、親チャンネルの履歴とスレッド内の履歴を時系列でマージして参照します。テキストチャンネルでメンションされた場合は、取得したチャンネル履歴に紐づくスレッド（メッセージに付いたスレッドや、アクティブなスレッドの開始メッセージが履歴内にあるもの）の内容も含めます。スレッド由来のメッセージには `[スレッド名]` プレフィックスが付きます。

### サーバーでの挙動

- **テキストチャンネルでのメンション** — そのメッセージからスレッドを作成し、メンション投稿へのリプライとしてスレッド内に返信します（既にスレッドが付いている場合はそこで継続）
- **スレッド内のメッセージ** — メンションなしでも応答します（初回のメンションでスレッドができたあとの会話用）
- **スレッド内でのメンション** — 上記と同様にスレッド内で返信します

Developer Portal で **Create Public Threads** と **Send Messages in Threads** 権限も付与してください。

## ランタイムでのモデル切り替え

環境変数の書き換えや再起動なしで、Discord 上でバックエンドやモデルを切り替えられます。
選択状態は `bot/.bot-model-state.json` に保存され、再起動後も維持されます。

使うバックエンドの API キー（`CURSOR_API_KEY` / `SAKANA_API_KEY` など）をあらかじめ設定しておいてください。

| コマンド | 説明 |
| --- | --- |
| `@bot /model` | 現在のモデルを表示 |
| `@bot /model list` | 利用可能なプリセット一覧 |
| `@bot /model cursor` | Cursor Auto に切り替え（新しいスレッドの既定も更新） |
| `@bot /model fugu-ultra` | Fugu Ultra に切り替え |
| `@bot /model cursor composer-2.5` | Cursor のモデルを明示指定 |

`モデル` でも同様に使えます（例: `@bot モデル list`）。

## 環境変数

| 変数 | 必須 | 説明 |
| --- | --- | --- |
| `DISCORD_BOT_TOKEN` | ✅ | Discord ボットのトークン |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | — | GitHub Personal Access Token。設定すると GitHub MCP が有効になる |
| `BOT_GITHUB_MCP_USER_IDS` | — | GitHub MCP を使える Discord ユーザー ID（カンマ区切り）。未設定なら制限なし |
| `CURSOR_API_KEY` | Cursor 利用時 | Cursor API キー（`/model cursor` で切り替え） |
| `BOT_CURSOR_CWD` | — | Cursor Local ランタイムの作業ディレクトリ（デフォルト: `bot/.cursor-bot-workspace`） |
| `SAKANA_API_KEY` | Fugu 利用時 | Sakana Fugu API キー（`/model fugu` などで切り替え） |
| `FUGU_BASE_URL` | — | API ベース URL（デフォルト: `https://api.sakana.ai`） |
| `BOT_FUGU_WEB_SEARCH` | — | Fugu の Web 検索ツールを有効にするか（デフォルト: `true`） |
| `BOT_ALLOWED_TOOLS` | — | 利用可能なツール(カンマ区切り。デフォルト: `WebSearch,WebFetch,Agent`) |
| `BOT_MAX_TURNS` | — | 1 回の応答あたりの最大ターン数(デフォルト: `12`) |
| `BOT_DISCORD_HISTORY_LIMIT` | — | 参照する Discord 履歴の件数(デフォルト: `100`、`0` で無効) |
| `BOT_REPLY_IN_THREAD` | — | チャンネルでのメンション時にスレッドを作成するか(デフォルト: `true`) |
| `BOT_MODEL_SWITCHING` | — | ランタイムでのモデル切り替えを有効にするか（デフォルト: `true`） |
| `BOT_MODEL_STATE_FILE` | — | モデル選択の保存先（デフォルト: `bot/.bot-model-state.json`） |

Web 検索・取得にはネットワーク接続が必要です。Claude 利用時は Anthropic API の認証も必要です。Cursor 利用時は Cursor サブスクの利用枠から消費されます。`WebSearch` は追加料金が発生する場合があります。Fugu 利用時は Sakana の料金体系に従います。
