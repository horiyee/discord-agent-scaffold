"""Runtime model selection without changing environment variables."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_STATE_FILE = Path(__file__).resolve().parents[2] / ".bot-model-state.json"


@dataclass(frozen=True, slots=True)
class ModelSelection:
    agent: str
    model: str | None = None

    @property
    def key(self) -> str:
        return f"{self.agent}:{self.model or 'default'}"

    def label(self) -> str:
        for preset in PRESETS.values():
            if preset.to_selection() == self:
                return preset.label
        if self.model:
            return f"{self.agent} ({self.model})"
        return self.agent


@dataclass(frozen=True, slots=True)
class ModelPreset:
    agent: str
    model: str | None
    label: str
    requires_env: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return f"{self.agent}:{self.model or 'default'}"

    def to_selection(self) -> ModelSelection:
        return ModelSelection(agent=self.agent, model=self.model)


PRESETS: dict[str, ModelPreset] = {
    "claude": ModelPreset(
        agent="claude",
        model=None,
        label="Claude Code（アカウント設定に従う）",
    ),
    "cursor": ModelPreset(
        agent="cursor",
        model=None,
        label="Cursor Auto / default",
        requires_env=("CURSOR_API_KEY",),
    ),
    "cursor-composer": ModelPreset(
        agent="cursor",
        model="composer-2.5",
        label="Cursor Composer 2.5",
        requires_env=("CURSOR_API_KEY",),
    ),
    "fugu": ModelPreset(
        agent="fugu",
        model="fugu",
        label="Sakana Fugu",
        requires_env=("SAKANA_API_KEY",),
    ),
    "fugu-ultra": ModelPreset(
        agent="fugu",
        model="fugu-ultra",
        label="Sakana Fugu Ultra",
        requires_env=("SAKANA_API_KEY",),
    ),
}

PRESET_ALIASES: dict[str, str] = {
    "cursor-auto": "cursor",
    "composer": "cursor-composer",
    "composer-2.5": "cursor-composer",
    "ultra": "fugu-ultra",
}


def switching_enabled() -> bool:
    raw = os.environ.get("BOT_MODEL_SWITCHING")
    if raw is None:
        return True
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def state_file_path() -> Path:
    raw = os.environ.get("BOT_MODEL_STATE_FILE")
    if raw:
        return Path(raw).expanduser()
    return DEFAULT_STATE_FILE


def infer_initial_default() -> ModelSelection:
    """Pick a sensible default when no persisted state exists yet."""
    presets = available_presets()
    if presets:
        return presets[0].to_selection()
    return ModelSelection(agent="claude")


def _selection_from_payload(payload: object) -> ModelSelection | None:
    if not isinstance(payload, dict):
        return None
    agent = str(payload.get("agent", "")).strip().lower()
    if not agent:
        return None
    model = payload.get("model")
    if model is not None:
        model = str(model).strip() or None
    return resolve_selection(agent, model) or ModelSelection(agent=agent, model=model)


def _env_available(preset: ModelPreset) -> bool:
    return all(os.environ.get(name, "").strip() for name in preset.requires_env)


def available_presets() -> list[ModelPreset]:
    presets: list[ModelPreset] = []
    seen: set[str] = set()
    for preset in PRESETS.values():
        if preset.key in seen:
            continue
        if preset.requires_env and not _env_available(preset):
            continue
        presets.append(preset)
        seen.add(preset.key)
    return presets


def resolve_selection(name: str, model: str | None = None) -> ModelSelection | None:
    normalized = name.strip().lower()
    if not normalized:
        return None

    alias = PRESET_ALIASES.get(normalized)
    if alias:
        normalized = alias

    preset = PRESETS.get(normalized)
    if preset is not None and _env_available(preset):
        return preset.to_selection()

    if model is not None:
        explicit_model = model.strip() or None
        if normalized == "claude":
            return ModelSelection(agent="claude")
        if normalized == "cursor" and os.environ.get("CURSOR_API_KEY", "").strip():
            return ModelSelection(agent="cursor", model=explicit_model)
        if normalized == "fugu" and os.environ.get("SAKANA_API_KEY", "").strip():
            return ModelSelection(agent="fugu", model=explicit_model or "fugu")
        return None

    if normalized == "claude":
        return ModelSelection(agent="claude")
    if normalized == "cursor" and os.environ.get("CURSOR_API_KEY", "").strip():
        return ModelSelection(agent="cursor")
    if normalized == "fugu" and os.environ.get("SAKANA_API_KEY", "").strip():
        return ModelSelection(agent="fugu", model="fugu")
    return None


class ModelSelectionStore:
    def __init__(
        self,
        *,
        default: ModelSelection | None = None,
        path: Path | None = None,
    ):
        self._path = path or state_file_path()
        self._default = default or infer_initial_default()
        self._selections: dict[str, ModelSelection] = {}
        self._load()

    @property
    def default(self) -> ModelSelection:
        return self._default

    def get(self, conversation_id: str) -> ModelSelection:
        return self._selections.get(conversation_id, self._default)

    def set(
        self,
        conversation_id: str,
        selection: ModelSelection,
        *,
        update_default: bool = True,
    ) -> None:
        if update_default:
            self._default = selection
        if selection == self._default:
            self._selections.pop(conversation_id, None)
        else:
            self._selections[conversation_id] = selection
        self._save()

    def scoped_conversation_id(self, conversation_id: str, selection: ModelSelection) -> str:
        return f"{conversation_id}:{selection.key}"

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("failed to load model selection state from %s", self._path)
            return

        loaded_default = _selection_from_payload(raw.get("default"))
        if loaded_default is not None:
            self._default = loaded_default

        conversations = raw.get("conversations", {})
        if not isinstance(conversations, dict):
            return
        for conversation_id, payload in conversations.items():
            selection = _selection_from_payload(payload)
            if selection is not None:
                self._selections[str(conversation_id)] = selection

    def _save(self) -> None:
        payload = {
            "default": asdict(self._default),
            "conversations": {
                conversation_id: asdict(selection)
                for conversation_id, selection in self._selections.items()
            },
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            logger.exception("failed to save model selection state to %s", self._path)


def parse_model_command(prompt: str) -> tuple[str, list[str]] | None:
    stripped = prompt.strip()
    if not stripped:
        return None
    head, _, rest = stripped.partition(" ")
    command = head.casefold()
    if command not in {"/model", "/モデル", "model", "モデル"}:
        return None
    args = rest.strip().split()
    return command, args


def format_status(selection: ModelSelection, *, default: ModelSelection) -> str:
    lines = [
        f"現在のモデル: **{selection.label()}**",
        f"全体の既定: {default.label()}",
        "",
        "切り替え: `/model <名前>`（新しいスレッドにも反映）",
        "一覧: `/model list`",
    ]
    return "\n".join(lines)


def format_preset_list(default: ModelSelection) -> str:
    lines = ["利用可能なモデル:"]
    for preset in available_presets():
        marker = " (既定)" if preset.to_selection() == default else ""
        lines.append(
            f"- `{preset.agent}` / プリセット `{_preset_command_name(preset)}` — {preset.label}{marker}"
        )
    lines.extend(
        [
            "",
            "例:",
            "- `/model cursor`",
            "- `/model fugu-ultra`",
            "- `/model cursor composer-2.5`",
        ]
    )
    return "\n".join(lines)


def _preset_command_name(preset: ModelPreset) -> str:
    for name, candidate in PRESETS.items():
        if candidate.key == preset.key:
            return name
    return preset.agent


def handle_model_command(args: list[str], store: ModelSelectionStore, conversation_id: str) -> str:
    if not switching_enabled():
        return "モデル切り替えは無効です（`BOT_MODEL_SWITCHING=false`）。"
    if not args:
        return format_status(store.get(conversation_id), default=store.default)
    if len(args) == 1 and args[0].casefold() == "list":
        return format_preset_list(store.default)

    selection: ModelSelection | None
    if len(args) == 1:
        selection = resolve_selection(args[0])
    else:
        selection = resolve_selection(args[0], args[1])

    if selection is None:
        available = ", ".join(_preset_command_name(preset) for preset in available_presets())
        return f"不明なモデルです。利用可能: {available}"

    store.set(conversation_id, selection, update_default=True)
    return f"モデルを **{selection.label()}** に切り替えました（新しいスレッドの既定も更新）。"
