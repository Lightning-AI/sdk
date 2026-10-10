"""OpenCode: add code.lightning.ai as the `lightning` provider without touching the rest of its config.

The provider block goes into the user's global config, spliced in so comments and other
settings stay as they are. The API key goes into OpenCode's own credential store,
auth.json, where `opencode auth login` keeps keys; OpenCode hands it to the provider of the
same id. Its metadata records which org and key `lightning code` set up.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

from lightning_sdk.cli.code import files
from lightning_sdk.cli.code.models import CODE_BASE_URL, REQUEST_TIMEOUT_MS, CodingModel
from lightning_sdk.cli.code.tool import (
    FileChange,
    KeyRecord,
    Plan,
    Tool,
    ToolConfigError,
    ToolState,
    default_to_set,
    emptied,
)
from lightning_sdk.utils import jsonc

PROVIDER_ID = "lightning"
SCHEMA_URL = "https://opencode.ai/config.json"
# marks the auth.json entries `lightning code` wrote, as opposed to ones a user added
MANAGED_BY = "lightning-sdk"

# Read in this order, later files winning; see OpenCode's config/config.ts.
_GLOBAL_CONFIG_FILES = ("config.json", "opencode.json", "opencode.jsonc")
_ENV_OVERRIDES = {
    "OPENCODE_CONFIG": "loads another config file on top of the global one",
    "OPENCODE_CONFIG_CONTENT": "puts inline config on top of the global one",
    "OPENCODE_AUTH_CONTENT": "replaces auth.json, so the key written there isn't used",
}


def _xdg_dir(variable: str, fallback: str) -> Path:
    # OpenCode uses xdg-basedir, which falls back to these paths on every platform, Windows included
    return Path(os.environ.get(variable) or Path.home() / fallback) / "opencode"


def config_dir() -> Path:
    return _xdg_dir("XDG_CONFIG_HOME", ".config")


def auth_path() -> Path:
    return _xdg_dir("XDG_DATA_HOME", ".local/share") / "auth.json"


def config_path() -> Path:
    """The global config file to edit: the one that wins when several exist, else a new opencode.json."""
    for name in reversed(_GLOBAL_CONFIG_FILES):
        path = config_dir() / name
        if path.exists():
            return path
    return config_dir() / "opencode.json"


def provider_config(models: Sequence[CodingModel]) -> dict[str, Any]:
    """The `provider.lightning` block. It has no apiKey: OpenCode reads that from auth.json.

    OpenCode sends at most 32,000 as max_tokens whatever ``limit.output`` says, and keeps
    prompts within ``limit.context`` minus that, so the full output limit is safe to state.
    """
    entries = {}
    for model in models:
        entry: dict[str, Any] = {"id": model.id, "name": model.name, "reasoning": model.reasoning}
        if model.reasoning:
            entry["interleaved"] = "reasoning_content"
        entry["tool_call"] = model.tools
        if model.images:
            entry["attachment"] = True
            entry["modalities"] = {"input": ["text", "image"], "output": ["text"]}
        entry["limit"] = {"context": model.context_window, "output": model.output_tokens}
        entries[model.key] = entry
    return {
        "npm": "@ai-sdk/openai-compatible",
        "name": "Lightning AI",
        "options": {"baseURL": CODE_BASE_URL, "timeout": REQUEST_TIMEOUT_MS},
        "models": entries,
    }


def model_ref(model: CodingModel) -> str:
    return f"{PROVIDER_ID}/{model.key}"


def _ours(ref: str) -> bool:
    return ref.startswith(f"{PROVIDER_ID}/")


@dataclass
class _Files:
    config_path: Path
    config_text: str
    auth_text: str
    auth: dict[str, Any]


def _project_configs(start: Path) -> list[Path]:
    """Project config files OpenCode would load in ``start``, walking up to the git root or home."""
    found = []
    home = Path.home()
    for directory in [start, *start.parents]:
        for name in ("opencode.json", "opencode.jsonc", ".opencode/opencode.json", ".opencode/opencode.jsonc"):
            path = directory / name
            if path.is_file() and path.parent != config_dir():
                found.append(path)
        if directory == home or (directory / ".git").exists():
            break
    return found


class OpenCode(Tool):
    id = "opencode"
    name = "OpenCode"
    binary = "opencode"
    install = "curl -fsSL https://opencode.ai/install | bash"
    start = "Start coding with `opencode`, and switch models with /models."

    def read(self) -> ToolState:
        path = config_path()
        text = files.read_text(path)
        try:
            config = jsonc.loads(text) if text.strip() else {}
            auth_text = files.read_text(auth_path())
            auth = json.loads(auth_text) if auth_text.strip() else {}
        except (jsonc.JSONCError, ValueError) as exc:
            raise ToolConfigError(str(exc)) from None
        if not isinstance(config, dict) or not isinstance(auth, dict):
            raise ToolConfigError(f"{path} or {auth_path()} is not a JSON object")

        entry = auth.get(PROVIDER_ID)
        credential = entry if isinstance(entry, dict) and entry.get("type") == "api" else None
        key = credential.get("key") if credential else None
        metadata = (credential or {}).get("metadata") or {}
        record = KeyRecord.from_dict(metadata) if metadata.get("managed_by") == MANAGED_BY else None
        provider = (config.get("provider") or {}).get(PROVIDER_ID) if isinstance(config.get("provider"), dict) else None
        model = config.get("model")
        return ToolState(
            record=record,
            key=key if isinstance(key, str) else None,
            configured=provider is not None or credential is not None,
            default_model=model if isinstance(model, str) else None,
            location=str(path),
            data=_Files(path, text, auth_text, auth),
        )

    def plan_setup(
        self,
        state: ToolState,
        *,
        models: Sequence[CodingModel],
        model: Optional[str],
        key: str,
        record: KeyRecord,
    ) -> Plan:
        current: _Files = state.data
        text = current.config_text
        if not text.strip():
            text = jsonc.set_value("", ["$schema"], SCHEMA_URL)
        text = jsonc.set_value(text, ["provider", PROVIDER_ID], provider_config(models))
        set_model = default_to_set(state.default_model, requested=model, models=models, ref=model_ref, ours=_ours)
        if set_model is not None:
            text = jsonc.set_value(text, ["model"], set_model)
        enabled = jsonc.get_value(text, ["enabled_providers"])
        if isinstance(enabled, list) and PROVIDER_ID not in enabled:
            # an allowlist of providers would hide ours
            text = jsonc.append_item(text, ["enabled_providers"], PROVIDER_ID)

        auth = dict(current.auth)
        auth[PROVIDER_ID] = {"type": "api", "key": key, "metadata": {"managed_by": MANAGED_BY, **record.as_dict()}}
        return Plan(
            changes=[
                FileChange(
                    auth_path(),
                    current.auth_text,
                    files.dump_json(auth),
                    mode=0o600,
                    secret=True,
                    summary=f"save the API key as '{PROVIDER_ID}'",
                    backup=False,
                ),
                FileChange(current.config_path, current.config_text, text),
            ],
            set_model=set_model,
        )

    def plan_remove(self, state: ToolState) -> Plan:
        current: _Files = state.data
        plan = Plan()
        text = current.config_text
        if jsonc.get_value(text, ["provider", PROVIDER_ID]) is not None:
            text = jsonc.remove_value(text, ["provider", PROVIDER_ID])
            if jsonc.get_value(text, ["provider"]) == {}:
                text = jsonc.remove_value(text, ["provider"])
            plan.removed.append(f"the {PROVIDER_ID} provider from {current.config_path}")
        # a default on the lightning provider can't work once the provider is gone, whoever set it
        if state.default_model and _ours(state.default_model):
            text = jsonc.remove_value(text, ["model"])
            plan.removed.append(f"the default model {state.default_model}")
        enabled = jsonc.get_value(text, ["enabled_providers"])
        if isinstance(enabled, list) and PROVIDER_ID in enabled:
            text = jsonc.remove_item(text, ["enabled_providers"], PROVIDER_ID)
            plan.removed.append(f"'{PROVIDER_ID}' from enabled_providers")
        plan.changes.append(
            FileChange(current.config_path, current.config_text, emptied(text, ignore=["$schema"]), backup=False)
        )

        if PROVIDER_ID in current.auth:
            auth = {k: v for k, v in current.auth.items() if k != PROVIDER_ID}
            plan.changes.append(
                FileChange(
                    auth_path(),
                    current.auth_text,
                    files.dump_json(auth),
                    mode=0o600,
                    secret=True,
                    summary=f"remove the '{PROVIDER_ID}' API key",
                    backup=False,
                )
            )
            plan.removed.append(f"the API key from {auth_path()}")
        return plan

    def summary(self, state: ToolState, plan: Plan) -> list[tuple[str, str]]:
        return [("Provider", f"{PROVIDER_ID} in {state.location}"), ("Key file", str(auth_path()))]

    def warnings(self, state: ToolState, *, cwd: Optional[Path] = None) -> list[str]:
        notes = [f"{name} is set, which {effect}." for name, effect in _ENV_OVERRIDES.items() if os.environ.get(name)]
        current: _Files = state.data
        config = jsonc.loads(current.config_text) if current.config_text.strip() else {}
        disabled = config.get("disabled_providers")
        if isinstance(disabled, list) and PROVIDER_ID in disabled:
            notes.append(f"disabled_providers in {current.config_path} includes '{PROVIDER_ID}'.")

        for path in _project_configs(cwd or Path.cwd()):
            try:
                project = jsonc.loads(files.read_text(path))
            except jsonc.JSONCError:
                continue
            if not isinstance(project, dict):
                continue
            if isinstance(project.get("provider"), dict) and PROVIDER_ID in project["provider"]:
                notes.append(f"{path} defines its own '{PROVIDER_ID}' provider, which wins in that project.")
            if "model" in project:
                notes.append(f"{path} sets model to {project['model']}, which wins in that project.")
        return notes
