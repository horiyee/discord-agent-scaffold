# discord-agent-scaffold

Discord AI agent bot を scaffold するための [Agent Skill](https://agentskills.io)
（Claude Agent SDK の厚いボイラープレート: スレッド、履歴、Web ツール、任意の GitHub MCP）。

Claude（Claude Code など skills 互換クライアント）や、Agent Skills オープン形式を
読む他のエージェントから利用できる。

## 構成

```text
discord-agent-scaffold/          # skill ディレクトリ（name と一致）
├── SKILL.md                     # メタデータ + agent 向け手順
├── assets/
│   └── bot/                     # 実行可能な厚いテンプレート
├── references/
│   └── template-overview.md     # 必要時に読む詳細
├── README.md
└── LICENSE
```

[Agent Skills 仕様](https://agentskills.io/specification) では型紙は `assets/`、
詳細は `references/`（オンデマンド）、`scripts/` は任意（現状なし）。

## skill としての入れ方

このディレクトリ（またはその clone）を、各クライアントの skills 配置に置く／symlink する。

- **Claude Code / Agent Skills**: クライアントの skills ディレクトリへ。フォルダ名は
  `discord-agent-scaffold` のままにする
- **Cursor**: 同様に `SKILL.md` を含むディレクトリを project / user skill として追加

frontmatter の `name` は `discord-agent-scaffold` で、**親ディレクトリ名と一致必須**。

### `.claude/skills` との関係

以前よくあった `リポ/.claude/skills/<name>/` は「そのリポで作業しているとき」向けの配置。
このリポの目的は **どこからでも bot を切るための配布用 skill** なので、リポ根が skill 本体
（`SKILL.md` + `assets/`）になっている今の形の方が向いている。

ローカルで Claude Code に読ませたい場合は、clone を
`~/.claude/skills/discord-agent-scaffold` などへ symlink すればよい
（中にさらに `.claude/skills` を切る必要はない）。

## 使い方

エージェントに Discord AI bot の scaffold（ペルソナ、役割、出力先）を頼む。
`SKILL.md` に従い `assets/bot/` をコピーし、システムプロンプトとスレ名を編集する。

## テンプレート bot を直接動かす

```sh
cd assets/bot
uv sync
export DISCORD_BOT_TOKEN=...
uv run bot
```

詳細は [`assets/bot/README.md`](assets/bot/README.md)。
