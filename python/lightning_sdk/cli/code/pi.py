"""pi: add code.lightning.ai as the `lightning` provider in ~/.pi/agent.

The provider goes into models.json, spliced in so the user's other providers and comments
stay. pi ignores the whole file when one entry is invalid, so only fields its schema
accepts are written. The key goes into pi's credential store, auth.json, where /login
keeps keys, and the default model into settings.json.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

from lightning_sdk.cli.code import files
from lightning_sdk.cli.code.models import CODE_BASE_URL, CodingModel
from lightning_sdk.cli.code.tool import (
    FileChange,
    KeyRecord,
    Plan,
    Tool,
    ToolConfigError,
    ToolState,
    default_to_set,
    emptied,
    record_change,
)
from lightning_sdk.utils import jsonc

PROVIDER_ID = "lightning"


def agent_dir() -> Path:
    return Path(os.environ.get("PI_CODING_AGENT_DIR") or Path.home() / ".pi" / "agent").expanduser()


def provider_config(models: Sequence[CodingModel]) -> dict[str, Any]:
    """The `providers.lightning` entry of models.json. The key isn't in it: pi reads that from auth.json."""
    return {
        "name": "Lightning AI",
        "baseUrl": CODE_BASE_URL,
        "api": "openai-completions",
        # lets code.lightning.ai keep a session on one replica, so its prompt cache is reused
        "compat": {"sendSessionAffinityHeaders": True},
        "models": [
            {
                "id": model.id,
                "name": model.name,
                "reasoning": model.reasoning,
                "input": ["text", "image"] if model.images else ["text"],
                "contextWindow": model.context_window,
                "maxTokens": model.output_tokens,
            }
            for model in models
        ],
    }


def model_ref(model: CodingModel) -> str:
    # pi's own reference, as `pi --model` takes it
    return f"{PROVIDER_ID}/{model.id}"


def _ours(ref: str) -> bool:
    return ref.startswith(f"{PROVIDER_ID}/")


@dataclass
class _Files:
    models_text: str
    auth_text: str
    auth: dict[str, Any]
    settings_text: str
    settings: dict[str, Any]


class Pi(Tool):
    id = "pi"
    name = "pi"
    binary = "pi"
    install = "curl -fsSL https://pi.dev/install.sh | sh"
    start = "Start coding with `pi`, and switch models with /model."

    def read(self) -> ToolState:
        directory = agent_dir()
        models_text = files.read_text(directory / "models.json")
        auth_text = files.read_text(directory / "auth.json")
        settings_text = files.read_text(directory / "settings.json")
        try:
            models_config = jsonc.loads(models_text) if models_text.strip() else {}
            auth = files.read_json(directory / "auth.json")
            settings = files.read_json(directory / "settings.json")
        except ValueError as exc:
            raise ToolConfigError(str(exc)) from None
        if not isinstance(models_config, dict):
            raise ToolConfigError(f"{directory / 'models.json'} is not a JSON object")

        providers = models_config.get("providers")
        provider = providers.get(PROVIDER_ID) if isinstance(providers, dict) else None
        credential = auth.get(PROVIDER_ID) if isinstance(auth.get(PROVIDER_ID), dict) else None
        key = credential.get("key") if credential else None
        default = None
        if settings.get("defaultProvider") and settings.get("defaultModel"):
            default = f"{settings['defaultProvider']}/{settings['defaultModel']}"
        record = KeyRecord.from_dict(files.load_record(self.id))
        return ToolState(
            # a record only counts while the tool still has a key to go with it
            record=record if credential is not None else None,
            key=key if isinstance(key, str) else None,
            configured=provider is not None or credential is not None,
            default_model=default,
            location=str(directory / "models.json"),
            data=_Files(models_text, auth_text, auth, settings_text, settings),
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
        directory = agent_dir()
        models_text = jsonc.set_value(current.models_text, ["providers", PROVIDER_ID], provider_config(models))

        auth = dict(current.auth)
        auth[PROVIDER_ID] = {"type": "api_key", "key": key}

        settings_text = current.settings_text
        set_model = default_to_set(state.default_model, requested=model, models=models, ref=model_ref, ours=_ours)
        if set_model is not None:
            model_id = set_model.split("/", 1)[1]
            settings_text = jsonc.set_value(settings_text, ["defaultProvider"], PROVIDER_ID)
            settings_text = jsonc.set_value(settings_text, ["defaultModel"], model_id)

        return Plan(
            changes=[
                FileChange(directory / "models.json", current.models_text, models_text),
                FileChange(
                    directory / "auth.json",
                    current.auth_text,
                    files.dump_json(auth),
                    mode=0o600,
                    secret=True,
                    summary=f"save the API key as '{PROVIDER_ID}'",
                ),
                FileChange(directory / "settings.json", current.settings_text, settings_text),
                record_change(self.id, record),
            ],
            set_model=set_model,
        )

    def plan_remove(self, state: ToolState) -> Plan:
        current: _Files = state.data
        directory = agent_dir()
        plan = Plan()
        models_text = current.models_text
        if jsonc.get_value(models_text, ["providers", PROVIDER_ID]) is not None:
            models_text = jsonc.remove_value(models_text, ["providers", PROVIDER_ID])
            plan.removed.append(f"the {PROVIDER_ID} provider from {directory / 'models.json'}")
        plan.changes.append(
            FileChange(directory / "models.json", current.models_text, emptied(models_text), backup=False)
        )

        if state.default_model and _ours(state.default_model):
            settings_text = jsonc.remove_value(current.settings_text, ["defaultProvider"])
            settings_text = jsonc.remove_value(settings_text, ["defaultModel"])
            plan.changes.append(
                FileChange(directory / "settings.json", current.settings_text, emptied(settings_text), backup=False)
            )
            plan.removed.append(f"the default model {state.default_model}")

        if PROVIDER_ID in current.auth:
            auth = {k: v for k, v in current.auth.items() if k != PROVIDER_ID}
            plan.changes.append(
                FileChange(
                    directory / "auth.json",
                    current.auth_text,
                    files.dump_json(auth),
                    mode=0o600,
                    secret=True,
                    summary=f"remove the '{PROVIDER_ID}' API key",
                    backup=False,
                )
            )
            plan.removed.append(f"the API key from {directory / 'auth.json'}")
        plan.changes.append(record_change(self.id, None))
        return plan

    def summary(self, state: ToolState, plan: Plan) -> list[tuple[str, str]]:
        return [("Provider", f"{PROVIDER_ID} in {state.location}"), ("Key file", str(agent_dir() / "auth.json"))]

    def warnings(self, state: ToolState) -> list[str]:
        current: _Files = state.data
        notes = []
        enabled = current.settings.get("enabledModels")
        if isinstance(enabled, list) and enabled and not any(str(m).startswith(f"{PROVIDER_ID}/") for m in enabled):
            notes.append(
                f"enabledModels in {agent_dir() / 'settings.json'} has no Lightning model, so /model hides them."
            )
        return notes
