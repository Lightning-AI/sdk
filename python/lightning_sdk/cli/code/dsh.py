"""DeepSeek Harness (dsh): add code.lightning.ai as the `lightning` model provider.

dsh composes each profile from bundled patch layers plus the user's
$DSH_HOME/profiles/<profile>/cordis.patch.yml, a YAML list of entries addressed by id.
Custom providers live in the `llm-pi-ai` entry and the default model in
`agent-default-model`, which is where its Settings page writes them too. Only those two
entries are rewritten; every other entry keeps its text and comments. The key goes into
dsh's credential file, $DSH_HOME/.credentials.yaml, under the name the provider reads.
"""

import copy
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

import yaml

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
    record_change,
)

PROVIDER_ID = "lightning"
# Not LIGHTNING_API_KEY, which dsh would derive from the provider id: that one holds the
# Lightning platform key in Studios, and the environment wins over the credential file.
KEY_ENV = "LIGHTNING_CODE_API_KEY"
PROVIDERS_ENTRY = "llm-pi-ai"
DEFAULT_ENTRY = "agent-default-model"
# the profiles `dsh web` and one-shot `dsh headless` runs boot
PROFILES = ("web", "headless")
PATCH_FILE = "cordis.patch.yml"


def dsh_home() -> Path:
    return Path(os.environ.get("DSH_HOME") or Path.home() / ".dsh").expanduser()


def patch_path(profile: str) -> Path:
    return dsh_home() / "profiles" / profile / PATCH_FILE


def credentials_path() -> Path:
    return dsh_home() / ".credentials.yaml"


def provider_config(models: Sequence[CodingModel]) -> dict[str, Any]:
    return {
        "displayName": "Lightning AI",
        "apiKeyEnv": KEY_ENV,
        "api": "openai-completions",
        "baseURL": CODE_BASE_URL,
        "models": [
            {
                "id": model.id,
                "name": model.name,
                "contextWindow": model.context_window,
                "maxTokens": model.output_tokens,
                "input": ["text", "image"] if model.images else ["text"],
            }
            for model in models
        ],
    }


def model_ref(model: CodingModel) -> str:
    return f"{PROVIDER_ID}/{model.id}"


def _ours(ref: str) -> bool:
    return ref.startswith(f"{PROVIDER_ID}/")


class _Tagged:
    """A value with a YAML tag PyYAML doesn't know, such as dsh's `!!js` expressions, kept as written."""

    def __init__(self, tag: str, value: Any) -> None:
        self.tag = tag
        self.value = value


class _Loader(yaml.SafeLoader):
    pass


class _Dumper(yaml.SafeDumper):
    pass


def _construct_tagged(loader: yaml.SafeLoader, suffix: str, node: yaml.Node) -> _Tagged:
    if isinstance(node, yaml.ScalarNode):
        value: Any = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    elif isinstance(node, yaml.MappingNode):
        value = loader.construct_mapping(node, deep=True)
    else:
        raise yaml.constructor.ConstructorError(None, None, f"unexpected node for tag {node.tag}", node.start_mark)
    return _Tagged(node.tag, value)


def _represent_tagged(dumper: yaml.SafeDumper, data: _Tagged) -> yaml.Node:
    if isinstance(data.value, list):
        return dumper.represent_sequence(data.tag, data.value)
    if isinstance(data.value, dict):
        return dumper.represent_mapping(data.tag, data.value)
    return dumper.represent_scalar(data.tag, data.value)


_Loader.add_multi_constructor("!", _construct_tagged)
_Loader.add_multi_constructor("tag:yaml.org,2002:js", _construct_tagged)
_Dumper.add_representer(_Tagged, _represent_tagged)


def _load(text: str, path: Path) -> list[Any]:
    try:
        data = yaml.load(text, Loader=_Loader) if text.strip() else []  # - SafeLoader subclass
    except yaml.YAMLError as exc:
        raise ToolConfigError(f"{path}: {exc}") from None
    if data is None:
        return []
    if not isinstance(data, list):
        raise ToolConfigError(f"{path} is not a YAML list of patch entries")
    return data


def _dump(entries: list[Any]) -> str:
    return yaml.dump(entries, Dumper=_Dumper, sort_keys=False, default_flow_style=False, allow_unicode=True)


def _item_spans(text: str, count: int) -> Optional[list[tuple[int, int]]]:
    """Line ranges of the top-level list items, or None when the text isn't a plain block list."""
    lines = text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.startswith("- ") or line.rstrip("\r\n") == "-"]
    if len(starts) != count:
        return None
    spans = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        # comments and blank lines just before the next item belong to it
        while end > start + 1 and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
            end -= 1
        spans.append((start, end))
    return spans


def _entry_id(entry: Any) -> Optional[str]:
    return entry.get("id") if isinstance(entry, dict) else None


def _set_entries(text: str, entries: list[Any], updates: dict[str, Optional[dict[str, Any]]]) -> str:
    """Replace, add or (with None) drop the entries with these ids, leaving the rest of the text as it is."""
    new_entries = []
    done = set()
    for entry in entries:
        entry_id = _entry_id(entry)
        if entry_id in updates:
            done.add(entry_id)
            if updates[entry_id] is not None:
                new_entries.append(updates[entry_id])
        else:
            new_entries.append(entry)
    new_entries += [entry for entry_id, entry in updates.items() if entry_id not in done and entry is not None]

    spans = _item_spans(text, len(entries)) if entries else None
    if spans is None:
        # empty, `[]`, or not a block list we can splice: write the whole list, keeping leading comments
        header = "".join(line for line in text.splitlines(keepends=True) if line.lstrip().startswith("#"))
        return header + (_dump(new_entries) if new_entries else "[]\n")

    lines = text.splitlines(keepends=True)
    out: list[str] = []
    previous_end = 0
    for (start, end), entry in zip(spans, entries):
        out += lines[previous_end:start]
        entry_id = _entry_id(entry)
        if entry_id in updates:
            if updates[entry_id] is not None:
                out.append(_dump([updates[entry_id]]))
        else:
            out += lines[start:end]
        previous_end = end
    out += lines[previous_end:]
    result = "".join(out)
    added = [entry for entry_id, entry in updates.items() if entry_id not in done and entry is not None]
    if added:
        if result and not result.endswith("\n"):
            result += "\n"
        result += _dump(added)
    return result if result.strip() else "[]\n"


def _find(entries: list[Any], entry_id: str) -> Optional[dict[str, Any]]:
    return next((e for e in entries if _entry_id(e) == entry_id), None)


def _with_provider(entry: Optional[dict[str, Any]], provider: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """The `llm-pi-ai` entry with our provider set, or removed when ``provider`` is None."""
    entry = copy.deepcopy(entry) if entry else {"id": PROVIDERS_ENTRY}
    config = entry.get("config")
    if not isinstance(config, dict):
        config = entry["config"] = {}
    providers = config.get("providers")
    if not isinstance(providers, dict):
        providers = config["providers"] = {}
    if provider is None:
        providers.pop(PROVIDER_ID, None)
        if not providers and set(config) == {"providers"} and set(entry) == {"id", "config"}:
            # the entry was only there for our provider
            return None
    else:
        providers[PROVIDER_ID] = provider
    return entry


@dataclass
class _Files:
    patches: dict[str, tuple[str, list[Any]]]
    credentials_text: str
    credentials: dict[str, Any]


class DeepSeekHarness(Tool):
    id = "dsh"
    name = "DeepSeek Harness"
    binary = "dsh"
    install = "npm install -g @deepseek-ai/dsh  (needs Node.js 22.19 or newer)"
    start = "Start coding with `dsh web`, and pick a Lightning model under Model in the message box."

    def read(self) -> ToolState:
        patches = {}
        for profile in PROFILES:
            path = patch_path(profile)
            text = files.read_text(path)
            patches[profile] = (text, _load(text, path))
        credentials_text = files.read_text(credentials_path())
        try:
            credentials = yaml.safe_load(credentials_text) if credentials_text.strip() else {}
        except yaml.YAMLError as exc:
            raise ToolConfigError(f"{credentials_path()}: {exc}") from None
        if not isinstance(credentials, dict):
            raise ToolConfigError(f"{credentials_path()} is not a YAML mapping")

        web = patches["web"][1]
        providers_entry = _find(web, PROVIDERS_ENTRY) or {}
        provider = ((providers_entry.get("config") or {}).get("providers") or {}).get(PROVIDER_ID)
        key = (credentials.get("refs") or {}).get(KEY_ENV)
        default_entry = (_find(web, DEFAULT_ENTRY) or {}).get("config") or {}
        default = None
        if default_entry.get("provider") and default_entry.get("model"):
            default = f"{default_entry['provider']}/{default_entry['model']}"
        record = KeyRecord.from_dict(files.load_record(self.id))
        return ToolState(
            record=record if key is not None else None,
            key=key if isinstance(key, str) else None,
            configured=provider is not None or key is not None,
            default_model=default,
            location=str(patch_path("web")),
            data=_Files(patches, credentials_text, credentials),
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
        set_model = default_to_set(state.default_model, requested=model, models=models, ref=model_ref, ours=_ours)
        plan = Plan(set_model=set_model)
        for profile in PROFILES:
            text, entries = current.patches[profile]
            updates: dict[str, Optional[dict[str, Any]]] = {
                PROVIDERS_ENTRY: _with_provider(_find(entries, PROVIDERS_ENTRY), provider_config(models))
            }
            if set_model is not None:
                updates[DEFAULT_ENTRY] = {
                    "id": DEFAULT_ENTRY,
                    "config": {"provider": PROVIDER_ID, "model": set_model.split("/", 1)[1]},
                }
            plan.changes.append(FileChange(patch_path(profile), text, _set_entries(text, entries, updates)))

        credentials = copy.deepcopy(current.credentials)
        credentials.setdefault("version", 1)
        refs = credentials.get("refs")
        credentials["refs"] = {**(refs if isinstance(refs, dict) else {}), KEY_ENV: key}
        plan.changes.append(
            FileChange(
                credentials_path(),
                current.credentials_text,
                yaml.safe_dump(credentials, sort_keys=False),
                mode=0o600,
                secret=True,
                summary=f"save the API key as {KEY_ENV}",
            )
        )
        plan.changes.append(record_change(self.id, record))
        return plan

    def plan_remove(self, state: ToolState) -> Plan:
        current: _Files = state.data
        plan = Plan()
        for profile in PROFILES:
            text, entries = current.patches[profile]
            updates: dict[str, Optional[dict[str, Any]]] = {}
            providers_entry = _find(entries, PROVIDERS_ENTRY)
            if providers_entry is not None:
                providers = ((providers_entry.get("config") or {}).get("providers")) or {}
                if PROVIDER_ID in providers:
                    updates[PROVIDERS_ENTRY] = _with_provider(providers_entry, None)
            default_entry = _find(entries, DEFAULT_ENTRY)
            if default_entry is not None and (default_entry.get("config") or {}).get("provider") == PROVIDER_ID:
                # dropping the entry brings back dsh's own default model
                updates[DEFAULT_ENTRY] = None
            if updates:
                plan.changes.append(
                    FileChange(patch_path(profile), text, _set_entries(text, entries, updates), backup=False)
                )
                plan.removed.append(f"the {PROVIDER_ID} provider from {patch_path(profile)}")
        if state.default_model and _ours(state.default_model):
            plan.removed.append(f"the default model {state.default_model}")

        refs = current.credentials.get("refs")
        if isinstance(refs, dict) and KEY_ENV in refs:
            credentials = copy.deepcopy(current.credentials)
            credentials["refs"].pop(KEY_ENV)
            plan.changes.append(
                FileChange(
                    credentials_path(),
                    current.credentials_text,
                    yaml.safe_dump(credentials, sort_keys=False),
                    mode=0o600,
                    secret=True,
                    summary=f"remove the {KEY_ENV} API key",
                    backup=False,
                )
            )
            plan.removed.append(f"the API key from {credentials_path()}")
        plan.changes.append(record_change(self.id, None))
        return plan

    def summary(self, state: ToolState, plan: Plan) -> list[tuple[str, str]]:
        return [
            ("Provider", f"{PROVIDER_ID} in the {' and '.join(PROFILES)} profiles under {dsh_home() / 'profiles'}"),
            ("Key file", f"{credentials_path()} ({KEY_ENV})"),
        ]

    def warnings(self, state: ToolState) -> list[str]:
        notes = []
        home_patch = dsh_home() / PATCH_FILE
        try:
            home_entries = _load(files.read_text(home_patch), home_patch)
        except ToolConfigError:
            home_entries = []
        for entry_id in (PROVIDERS_ENTRY, DEFAULT_ENTRY):
            if _find(home_entries, entry_id) is not None:
                notes.append(f"{home_patch} sets '{entry_id}', which overrides the profiles.")
        if os.environ.get(KEY_ENV):
            notes.append(f"{KEY_ENV} is set in your environment, and dsh uses it instead of the saved key.")
        return notes
