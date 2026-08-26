---
name: discord-agent-scaffold
description: >-
  Claude / Cursor / Sakana Fugu ベースの厚い Discord AI agent bot テンプレートから、
  カスタム bot を scaffold する（メンション/DM、スレッド返信、チャンネル履歴、
  WebSearch/WebFetch、任意の GitHub MCP）。新規 Discord bot 作成、Discord AI
  agent の立ち上げ、このテンプレートからのペルソナカスタマイズ時に使う。
license: MIT
compatibility: Python 3.14+、uv、Discord bot token。Claude 利用時は Claude Code 認証または ANTHROPIC_API_KEY。Cursor 利用時は CURSOR_API_KEY。Fugu 利用時は SAKANA_API_KEY。GitHub MCP 利用時は Node.js/npx。
metadata:
  author: horiyee
  version: "0.1"
---

# Discord AI agent bot を scaffold する

[`assets/bot/`](assets/bot/) の厚いテンプレートをコピーし、ペルソナ／味付けを適用する。
Discord や Claude の配線をゼロから書き直さない。

設計の詳細は [`references/template-overview.md`](references/template-overview.md) を参照。

## いつ使うか

- 新しい Discord AI / agent bot を作りたいとき
- `discord-agent-scaffold` から scaffold したいとき
- メンション／DM＋スレッド UX の上に独自ペルソナを載せたいとき

## `assets/bot` に既にあるもの

| 領域 | 挙動 |
| --- | --- |
| トリガー | ギルドは初回 `@mention`（スレ内はメンション不要）または DM |
| スレッド | テキストチャンネルでのメンションからスレッドを作成し、その中に返信 |
| コンテキスト | 直近履歴＋リプライチェーン＋関連スレ。発言者の表示名をプロンプトに含める |
| Agent | `BOT_AGENT` で Claude / Cursor / Sakana Fugu。認証／利用上限エラーは日本語で返す |
| ツール | Claude: `WebSearch` / `WebFetch` / `Agent`。Cursor: SDK エージェント。Fugu: `web_search` |
| MCP | Claude / Cursor 利用時、`GITHUB_PERSONAL_ACCESS_TOKEN` で GitHub MCP |
| モデル | Claude はアカウント設定。Cursor は `BOT_MODEL`（未設定なら Auto）。Fugu は `FUGU_MODEL` |

## 手順

### 1. 味付けを集める

足りなければ聞く: bot 名、ペルソナ／口調、役割／ドメイン、既定スレッド名、
出力先パス。任意: モデル、Web ツール／GitHub MCP を残すか。

### 2. テンプレートをコピーする

パッケージ全体をコピーする（薄くしない）:

```text
assets/bot/  →  <destination>/bot/
```

`assets/bot` はこの skill ルート（この `SKILL.md` があるディレクトリ）からの相対パス。

```sh
cp -R assets/bot <destination>/bot
```

`pyproject.toml`、`uv.lock`、`.python-version`、`src/bot/**`、`src/mcp_servers/**`、
テンプレート README は残す。

### 3. 味付けを適用する

| 場所 | 変更内容 |
| --- | --- |
| `src/bot/agents/prompts.py` → `DEFAULT_SYSTEM_PROMPT` | ペルソナ＋役割 |
| `src/bot/platforms/discord.py` → `DEFAULT_THREAD_NAME` | 空プロンプト時のスレ名 |
| `README.md` / `pyproject.toml` | 名前、用途、authors |

バグ修正以外ではプラットフォーム側モジュールを触らない。

### 4. 起動手順を渡す

1. Discord アプリで **Message Content Intent** を有効化
2. Send Messages / Create Public Threads / Send Messages in Threads / Read Message History で招待
3. `cd bot && uv sync`
4. `DISCORD_BOT_TOKEN` を export（＋ Claude 認証または `ANTHROPIC_API_KEY`）
5. `uv run bot`
6. ギルドで `@mention`（スレッド作成を期待）。以降はそのスレ内ではメンション不要。または DM

## やってはいけないこと

- `assets/bot` をコピーせず薄いスタブを自作する
- 頼まれていないのに履歴／MCP／Web ツールを削る
- トークンやシークレットをコミットする
