"""Codex: a `lightning` profile, used with `codex --profile lightning`.

Codex layers $CODEX_HOME/<name>.config.toml over config.toml when started with
--profile <name>, so the whole setup lives in a file of our own and the user's config.toml
and default model stay as they are. The file holds the key, so only the user can read it.
Codex only speaks the Responses API to custom providers, which code.lightning.ai serves.
"""

import os
from pathlib import Path
from typing import Any, Optional, Sequence

import tomllib

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
    record_change,
)

PROFILE = "lightning"
PROVIDER_ID = "lightning"
# the first line of a profile `lightning code` wrote
MARKER = "# Written by `lightning code setup codex`."
# Codex caps the context of models it doesn't know at this many tokens
_MAX_UNKNOWN_CONTEXT = 272_000


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()


def profile_path() -> Path:
    return codex_home() / f"{PROFILE}.config.toml"


def _toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def profile_text(models: Sequence[CodingModel], *, model: str, key: str) -> str:
    # one context window covers every model, since -m switches between them in the same profile
    context = min(min(m.context_window for m in models), _MAX_UNKNOWN_CONTEXT)
    names = ", ".join(m.id for m in models)
    return f"""{MARKER} Use it with: codex --profile {PROFILE}
# Run the setup again to update it; `lightning code remove codex` deletes it.
# Models: {names}
model_provider = "{PROVIDER_ID}"
model = {_toml_string(model)}
model_context_window = {context}
model_reasoning_summary = "none"

[model_providers.{PROVIDER_ID}]
name = "Lightning AI"
base_url = "{CODE_BASE_URL}"
wire_api = "responses"
experimental_bearer_token = {_toml_string(key)}
stream_idle_timeout_ms = {REQUEST_TIMEOUT_MS}
"""


def model_ref(model: CodingModel) -> str:
    return model.id


class Codex(Tool):
    id = "codex"
    name = "Codex"
    binary = "codex"
    install = "npm install -g @openai/codex"
    start = f"Start coding with `codex --profile {PROFILE}`, and switch models with -m <model id>."

    def read(self) -> ToolState:
        path = profile_path()
        text = files.read_text(path)
        try:
            profile: dict[str, Any] = tomllib.loads(text) if text.strip() else {}
        except tomllib.TOMLDecodeError as exc:
            raise ToolConfigError(f"{path}: {exc}") from None
        provider = (profile.get("model_providers") or {}).get(PROVIDER_ID) or {}
        key = provider.get("experimental_bearer_token")
        ours = text.startswith(MARKER)
        record = KeyRecord.from_dict(files.load_record(self.id)) if ours else None
        model = profile.get("model")
        return ToolState(
            record=record,
            key=key if isinstance(key, str) and ours else None,
            configured=bool(text.strip()),
            default_model=model if isinstance(model, str) else None,
            location=str(path),
            data=text,
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
        # the profile only ever holds Lightning models, so a default not served any more is replaced
        set_model = default_to_set(
            state.default_model, requested=model, models=models, ref=model_ref, ours=lambda ref: True
        )
        chosen = set_model or state.default_model or ""
        text = profile_text(models, model=chosen, key=key)
        return Plan(
            changes=[
                FileChange(profile_path(), state.data, text, mode=0o600, secret=True),
                record_change(self.id, record),
            ],
            set_model=set_model,
        )

    def plan_remove(self, state: ToolState) -> Plan:
        plan = Plan(changes=[record_change(self.id, None)])
        if state.configured:
            plan.changes.insert(0, FileChange(profile_path(), state.data, None, secret=True, backup=False))
            plan.removed.append(f"the {PROFILE} profile {profile_path()}")
        return plan

    def summary(self, state: ToolState, plan: Plan) -> list[tuple[str, str]]:
        return [("Profile", f"{profile_path()} (holds the API key)")]

    def warnings(self, state: ToolState) -> list[str]:
        config = codex_home() / "config.toml"
        try:
            user = tomllib.loads(files.read_text(config))
        except tomllib.TOMLDecodeError:
            return [f"{config} isn't valid TOML, so Codex won't start until it's fixed."]
        notes = []
        if PROFILE in (user.get("profiles") or {}):
            notes.append(f"{config} has a [profiles.{PROFILE}] table, which makes `codex --profile {PROFILE}` fail.")
        if PROVIDER_ID in (user.get("model_providers") or {}):
            notes.append(f"{config} defines [model_providers.{PROVIDER_ID}], which the profile overrides.")
        return notes
