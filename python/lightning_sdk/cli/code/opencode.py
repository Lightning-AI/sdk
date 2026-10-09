"""OpenCode: add code.lightning.ai as the `lightning` provider without touching the rest of its config.

The provider block goes into the user's global config, spliced in so comments and other
settings stay as they are. The API key goes into OpenCode's own credential store,
auth.json, where `opencode auth login` keeps keys; OpenCode hands it to the provider of the
same id. Its metadata records which org and key `lightning code` set up, for re-runs,
`lightning code status` and `lightning code remove`.
"""

import difflib
import json
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from lightning_sdk.cli.code.models import (
    CODE_BASE_URL,
    CODING_MODELS,
    DEFAULT_MODEL,
    OUTPUT_TOKENS,
    REQUEST_TIMEOUT_MS,
)
from lightning_sdk.utils import jsonc

NAME = "OpenCode"
PROVIDER_ID = "lightning"
SCHEMA_URL = "https://opencode.ai/config.json"
INSTALL_COMMAND = "curl -fsSL https://opencode.ai/install | bash"
# marks the auth.json entries `lightning code` wrote, as opposed to ones a user added
MANAGED_BY = "lightning-sdk"
BACKUP_SUFFIX = ".lightning-backup"

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


def provider_config() -> dict[str, Any]:
    """The `provider.lightning` block. It has no apiKey: OpenCode reads that from auth.json."""
    models = {}
    for model in CODING_MODELS:
        entry: dict[str, Any] = {
            "id": model.id,
            "name": model.name,
            "reasoning": True,
            "tool_call": True,
            "interleaved": "reasoning_content",
        }
        if model.images:
            entry["attachment"] = True
            entry["modalities"] = {"input": ["text", "image"], "output": ["text"]}
        entry["limit"] = {"context": model.context_window, "output": OUTPUT_TOKENS}
        models[model.key] = entry
    return {
        "npm": "@ai-sdk/openai-compatible",
        "name": "Lightning AI",
        "options": {"baseURL": CODE_BASE_URL, "timeout": REQUEST_TIMEOUT_MS},
        "models": models,
    }


def model_ref(model_key: str) -> str:
    return f"{PROVIDER_ID}/{model_key}"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _write(path: Path, text: str, *, mode: Optional[int] = None) -> None:
    """Replace ``path`` atomically, keeping its permissions unless ``mode`` is given."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode is None:
        mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    tmp = path.with_name(f".{path.name}.lightning-tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


@dataclass
class Credential:
    """The `lightning` entry in auth.json."""

    key: str
    metadata: dict[str, str]

    @property
    def managed(self) -> bool:
        return self.metadata.get("managed_by") == MANAGED_BY

    @property
    def org_id(self) -> Optional[str]:
        return self.metadata.get("org_id")

    @property
    def key_id(self) -> Optional[str]:
        return self.metadata.get("key_id")


@dataclass
class State:
    """What OpenCode's files say about the Lightning setup right now."""

    config_path: Path
    config_text: str
    auth: dict[str, Any]
    credential: Optional[Credential]

    @property
    def provider(self) -> Optional[Any]:
        return jsonc.get_value(self.config_text, ["provider", PROVIDER_ID])

    @property
    def model(self) -> Optional[str]:
        return jsonc.get_value(self.config_text, ["model"])

    @property
    def managed(self) -> bool:
        return self.credential is not None and self.credential.managed

    @property
    def foreign(self) -> bool:
        """Whether a `lightning` provider or key exists that `lightning code` didn't write."""
        return not self.managed and (self.provider is not None or self.credential is not None)


def read_state() -> State:
    """Read the global config and auth.json. Raises ``jsonc.JSONCError`` if either can't be parsed."""
    path = config_path()
    text = _read(path)
    if text.strip():
        jsonc.loads(text)

    auth_text = _read(auth_path())
    auth = json.loads(auth_text) if auth_text.strip() else {}
    if not isinstance(auth, dict):
        raise jsonc.JSONCError(f"{auth_path()} is not a JSON object")
    entry = auth.get(PROVIDER_ID)
    credential = None
    if isinstance(entry, dict) and entry.get("type") == "api" and isinstance(entry.get("key"), str):
        credential = Credential(entry["key"], dict(entry.get("metadata") or {}))
    return State(path, text, auth, credential)


@dataclass
class Plan:
    """The changes `setup` makes, worked out before anything is written."""

    state: State
    config_text: str
    set_model: Optional[str]

    def config_diff(self) -> str:
        before = self.state.config_text.splitlines(keepends=True)
        after = self.config_text.splitlines(keepends=True)
        name = str(self.state.config_path)
        return "".join(difflib.unified_diff(before, after, fromfile=name, tofile=name))


def plan_setup(state: State, *, model: Optional[str]) -> Plan:
    """Work out the new config: our provider block, and `model` only when asked or unset.

    ``model`` is a model key passed with --model; without it the default model is set only
    when the user has no default of their own.
    """
    text = state.config_text
    if not text.strip():
        text = jsonc.set_value("", ["$schema"], SCHEMA_URL)
    text = jsonc.set_value(text, ["provider", PROVIDER_ID], provider_config())

    set_model = None
    if model is not None:
        set_model = model_ref(model)
    elif state.model is None:
        set_model = model_ref(DEFAULT_MODEL)
    if set_model is not None:
        text = jsonc.set_value(text, ["model"], set_model)
    return Plan(state, text, set_model)


def apply_setup(plan: Plan, *, key: str, metadata: dict[str, str]) -> Optional[Path]:
    """Write auth.json and the config. Returns the backup of the config, if there was one to back up."""
    state = plan.state
    auth = dict(state.auth)
    auth[PROVIDER_ID] = {"type": "api", "key": key, "metadata": {"managed_by": MANAGED_BY, **metadata}}
    _write(auth_path(), json.dumps(auth, indent=2) + "\n", mode=0o600)

    backup = None
    if plan.config_text != state.config_text:
        if state.config_text:
            backup = state.config_path.with_name(state.config_path.name + BACKUP_SUFFIX)
            shutil.copy2(state.config_path, backup)
        _write(state.config_path, plan.config_text)
    return backup


def remove(state: State) -> list[str]:
    """Remove the provider, a default model on it, and the key. Returns what was removed."""
    removed = []
    text = state.config_text
    if state.provider is not None:
        text = jsonc.remove_value(text, ["provider", PROVIDER_ID])
        if jsonc.get_value(text, ["provider"]) == {}:
            text = jsonc.remove_value(text, ["provider"])
        removed.append(f"the {PROVIDER_ID} provider from {state.config_path}")
    # a default on the lightning provider can't work once the provider is gone, whoever set it
    if isinstance(state.model, str) and state.model.startswith(f"{PROVIDER_ID}/"):
        text = jsonc.remove_value(text, ["model"])
        removed.append(f"the default model {state.model}")
    if text != state.config_text:
        _write(state.config_path, text)

    if state.credential is not None:
        auth = {k: v for k, v in state.auth.items() if k != PROVIDER_ID}
        _write(auth_path(), json.dumps(auth, indent=2) + "\n", mode=0o600)
        removed.append(f"the API key from {auth_path()}")
    return removed


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


def warnings(state: State, *, cwd: Optional[Path] = None) -> list[str]:
    """Settings elsewhere that would stop OpenCode from using what `setup` wrote."""
    notes = [f"{name} is set, which {effect}." for name, effect in _ENV_OVERRIDES.items() if os.environ.get(name)]

    config = jsonc.loads(state.config_text) if state.config_text.strip() else {}
    enabled = config.get("enabled_providers")
    if isinstance(enabled, list) and PROVIDER_ID not in enabled:
        notes.append(f"enabled_providers in {state.config_path} doesn't include '{PROVIDER_ID}'.")
    disabled = config.get("disabled_providers")
    if isinstance(disabled, list) and PROVIDER_ID in disabled:
        notes.append(f"disabled_providers in {state.config_path} includes '{PROVIDER_ID}'.")

    for path in _project_configs(cwd or Path.cwd()):
        try:
            project = jsonc.loads(_read(path))
        except jsonc.JSONCError:
            continue
        if not isinstance(project, dict):
            continue
        if isinstance(project.get("provider"), dict) and PROVIDER_ID in project["provider"]:
            notes.append(f"{path} defines its own '{PROVIDER_ID}' provider, which wins in that project.")
        if "model" in project:
            notes.append(f"{path} sets model to {project['model']}, which wins in that project.")
    return notes


def installed() -> bool:
    return shutil.which("opencode") is not None
