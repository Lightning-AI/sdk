"""pi, Codex, DeepSeek Harness and Cursor, through `lightning code setup`, `status` and `remove`."""

import json
import stat
from pathlib import Path

import pytest
import tomllib
import yaml
from click.testing import CliRunner

from lightning_sdk.cli.code import codex, dsh, files, pi
from lightning_sdk.cli.code.remove import remove
from lightning_sdk.cli.code.setup import setup
from lightning_sdk.cli.code.status import status
from lightning_sdk.utils import jsonc
from tests.cli.code.conftest import KEY, invoke


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _records() -> dict:
    return json.loads(files.records_path().read_text())


def _no_backups(directory: Path) -> None:
    assert not list(directory.rglob(f"*{files.BACKUP_SUFFIX}"))


# pi


PI_MODELS = """{
  // my own provider
  "providers": {
    "ollama": {"baseUrl": "http://localhost:11434/v1", "api": "openai-completions", "models": [{"id": "qwen"}]}
  }
}
"""


def test_pi_setup_writes_provider_key_and_default(api) -> None:
    assert invoke(setup, "pi").exit_code == 0

    directory = pi.agent_dir()
    provider = jsonc.loads((directory / "models.json").read_text())["providers"]["lightning"]
    assert provider["baseUrl"] == "https://code.lightning.ai/v1"
    assert provider["api"] == "openai-completions"
    assert "apiKey" not in provider
    flash = next(model for model in provider["models"] if model["id"] == "lightning-ai/deepseek-v4.1-flash")
    assert flash == {
        "id": "lightning-ai/deepseek-v4.1-flash",
        "name": "DeepSeek V4.1 Flash",
        "reasoning": True,
        "input": ["text", "image"],
        "contextWindow": 253_952,
        "maxTokens": 131_072,
    }
    assert json.loads((directory / "auth.json").read_text()) == {"lightning": {"type": "api_key", "key": KEY}}
    assert _mode(directory / "auth.json") == 0o600
    assert json.loads((directory / "settings.json").read_text()) == {
        "defaultProvider": "lightning",
        "defaultModel": "lightning-ai/deepseek-v4.1-flash",
    }
    assert _records()["pi"] == {"managed": True}


def test_pi_keeps_the_users_providers_default_and_keys(api) -> None:
    directory = pi.agent_dir()
    directory.mkdir(parents=True)
    (directory / "models.json").write_text(PI_MODELS)
    (directory / "settings.json").write_text('{\n  "defaultProvider": "ollama",\n  "defaultModel": "qwen"\n}\n')
    (directory / "auth.json").write_text('{"anthropic": {"type": "api_key", "key": "sk-ant"}}')

    result = invoke(setup, "pi")
    assert result.exit_code == 0
    assert "Default" not in result.output

    text = (directory / "models.json").read_text()
    assert "// my own provider" in text
    assert set(jsonc.loads(text)["providers"]) == {"ollama", "lightning"}
    assert json.loads((directory / "settings.json").read_text())["defaultProvider"] == "ollama"
    assert json.loads((directory / "auth.json").read_text())["anthropic"] == {"type": "api_key", "key": "sk-ant"}
    # the user's models.json is backed up, the key file isn't
    assert (directory / "models.json.lightning-backup").read_text() == PI_MODELS
    assert not (directory / "auth.json.lightning-backup").exists()

    assert invoke(remove, "pi").exit_code == 0
    assert (directory / "models.json").read_text() == PI_MODELS
    assert json.loads((directory / "auth.json").read_text()) == {"anthropic": {"type": "api_key", "key": "sk-ant"}}
    assert json.loads((directory / "settings.json").read_text())["defaultModel"] == "qwen"


def test_pi_remove_deletes_the_files_setup_created(api) -> None:
    assert invoke(setup, "pi").exit_code == 0
    result = invoke(remove, "pi")

    assert result.exit_code == 0
    directory = pi.agent_dir()
    assert not (directory / "models.json").exists()
    assert not (directory / "settings.json").exists()
    assert json.loads((directory / "auth.json").read_text()) == {}
    assert "pi" not in _records()


def test_pi_hand_made_provider_needs_force(api) -> None:
    directory = pi.agent_dir()
    directory.mkdir(parents=True)
    (directory / "models.json").write_text('{"providers": {"lightning": {"apiKey": "sk-lit-pasted"}}}')

    result = CliRunner().invoke(setup, ["pi"])
    assert result.exit_code == 1
    assert "--force" in result.output
    assert invoke(setup, "pi", "--force").exit_code == 0
    assert "apiKey" not in jsonc.loads((directory / "models.json").read_text())["providers"]["lightning"]


# Codex


def test_codex_setup_writes_only_its_profile(api, tool_homes: Path) -> None:
    home = codex.codex_home()
    home.mkdir(parents=True)
    (home / "config.toml").write_text('model = "gpt-5"\n# mine\n')

    result = invoke(setup, "codex")
    assert result.exit_code == 0
    assert "codex --profile lightning" in result.output

    assert (home / "config.toml").read_text() == 'model = "gpt-5"\n# mine\n'
    path = codex.profile_path()
    assert path.name == "lightning.config.toml"
    assert _mode(path) == 0o600
    text = path.read_text()
    assert text.startswith(codex.MARKER)
    profile = tomllib.loads(text)
    assert profile["model_provider"] == "lightning"
    assert profile["model"] == "lightning-ai/deepseek-v4.1-flash"
    assert profile["model_context_window"] == 253_952
    assert profile["model_providers"]["lightning"] == {
        "name": "Lightning AI",
        "base_url": "https://code.lightning.ai/v1",
        "wire_api": "responses",
        "experimental_bearer_token": KEY,
        "stream_idle_timeout_ms": 600_000,
    }
    _no_backups(tool_homes)


def test_codex_rerun_keeps_the_key_and_a_model_picked_in_codex(api) -> None:
    assert invoke(setup, "codex").exit_code == 0
    # Codex's /model writes the profile's model
    path = codex.profile_path()
    path.write_text(
        path.read_text().replace('model = "lightning-ai/deepseek-v4.1-flash"', 'model = "lightning-ai/glm-5.3"')
    )

    assert invoke(setup, "codex").exit_code == 0
    profile = tomllib.loads(path.read_text())
    assert profile["model"] == "lightning-ai/glm-5.3"
    assert profile["model_providers"]["lightning"]["experimental_bearer_token"] == KEY

    assert invoke(setup, "codex", "--model", "glm-5.3-flash").exit_code == 0
    assert tomllib.loads(path.read_text())["model"] == "lightning-ai/glm-5.3-flash"


def test_codex_replaces_a_retired_model(api) -> None:
    assert invoke(setup, "codex").exit_code == 0
    path = codex.profile_path()
    path.write_text(
        path.read_text().replace('model = "lightning-ai/deepseek-v4.1-flash"', 'model = "lightning-ai/glm-4"')
    )
    assert tomllib.loads(path.read_text())["model"] == "lightning-ai/glm-4"
    assert invoke(setup, "codex").exit_code == 0
    assert tomllib.loads(path.read_text())["model"] == "lightning-ai/deepseek-v4.1-flash"


def test_codex_profile_it_did_not_write_needs_force(api) -> None:
    codex.codex_home().mkdir(parents=True)
    codex.profile_path().write_text('model = "mine"\n')

    result = CliRunner().invoke(setup, ["codex"])
    assert result.exit_code == 1
    assert "--force" in result.output
    assert codex.profile_path().read_text() == 'model = "mine"\n'


def test_codex_remove_deletes_the_profile(api) -> None:
    assert invoke(setup, "codex").exit_code == 0
    assert invoke(remove, "codex").exit_code == 0
    assert not codex.profile_path().exists()


def test_codex_dry_run_masks_the_key(api) -> None:
    assert invoke(setup, "codex").exit_code == 0
    result = invoke(setup, "codex", "--dry-run")
    assert KEY not in result.output
    assert "lit_sa_" not in result.output


def test_codex_warns_about_a_legacy_profile_table() -> None:
    codex.codex_home().mkdir(parents=True)
    (codex.codex_home() / "config.toml").write_text("[profiles.lightning]\nmodel = 'x'\n")
    tool = codex.Codex()
    assert any("[profiles.lightning]" in note for note in tool.warnings(tool.read()))


# DeepSeek Harness


DSH_PATCH = """# my dsh tweaks
- id: session-title
  config:
    fallbackMaxWords: 7   # keep titles short

- id: hmr
  disabled: !!js "!ctx.get('profileContext')"
"""


def _patch(profile: str = "web") -> list:
    return yaml.load(dsh.patch_path(profile).read_text(), Loader=dsh._Loader)


def test_dsh_setup_writes_both_profiles_and_the_key(api) -> None:
    result = invoke(setup, "dsh")
    assert result.exit_code == 0

    for profile in ("web", "headless"):
        entries = {entry["id"]: entry for entry in _patch(profile)}
        provider = entries["llm-pi-ai"]["config"]["providers"]["lightning"]
        assert provider["apiKeyEnv"] == "LIGHTNING_CODE_API_KEY"
        assert provider["api"] == "openai-completions"
        assert provider["baseURL"] == "https://code.lightning.ai/v1"
        assert len(provider["models"]) == 3
        assert entries["agent-default-model"]["config"] == {
            "provider": "lightning",
            "model": "lightning-ai/deepseek-v4.1-flash",
        }

    credentials = yaml.safe_load(dsh.credentials_path().read_text())
    assert credentials == {"version": 1, "refs": {"LIGHTNING_CODE_API_KEY": KEY}}
    assert _mode(dsh.credentials_path()) == 0o600


def test_dsh_splices_into_the_users_patch_and_remove_restores_it(api) -> None:
    dsh.patch_path("web").parent.mkdir(parents=True)
    dsh.patch_path("web").write_text(DSH_PATCH)

    assert invoke(setup, "dsh").exit_code == 0
    text = dsh.patch_path("web").read_text()
    assert text.startswith(DSH_PATCH)
    assert "!!js \"!ctx.get('profileContext')\"" in text
    assert {entry["id"] for entry in _patch()} == {"session-title", "hmr", "llm-pi-ai", "agent-default-model"}

    assert invoke(remove, "dsh").exit_code == 0
    assert dsh.patch_path("web").read_text() == DSH_PATCH
    assert yaml.safe_load(dsh.credentials_path().read_text())["refs"] == {}


def test_dsh_keeps_the_users_default_and_other_providers(api) -> None:
    dsh.patch_path("web").parent.mkdir(parents=True)
    dsh.patch_path("web").write_text(
        "- id: llm-pi-ai\n"
        "  config:\n"
        "    providers:\n"
        "      mine: {api: openai-completions, baseURL: 'http://localhost:8000/v1', models: [{id: m}]}\n"
        "- id: agent-default-model\n"
        "  config: {provider: mine, model: m}\n"
    )
    assert invoke(setup, "dsh").exit_code == 0

    entries = {entry["id"]: entry for entry in _patch()}
    assert set(entries["llm-pi-ai"]["config"]["providers"]) == {"mine", "lightning"}
    assert entries["agent-default-model"]["config"] == {"provider": "mine", "model": "m"}

    assert invoke(remove, "dsh").exit_code == 0
    entries = {entry["id"]: entry for entry in _patch()}
    assert set(entries["llm-pi-ai"]["config"]["providers"]) == {"mine"}
    assert entries["agent-default-model"]["config"] == {"provider": "mine", "model": "m"}


def test_dsh_keeps_other_credentials(api) -> None:
    dsh.dsh_home().mkdir(parents=True)
    dsh.credentials_path().write_text("version: 1\nrefs:\n  DEEPSEEK_API_KEY: sk-ds\nrecords: {}\n")
    assert invoke(setup, "dsh").exit_code == 0
    assert yaml.safe_load(dsh.credentials_path().read_text())["refs"] == {
        "DEEPSEEK_API_KEY": "sk-ds",
        "LIGHTNING_CODE_API_KEY": KEY,
    }
    assert not dsh.credentials_path().with_name(".credentials.yaml.lightning-backup").exists()

    result = invoke(setup, "dsh", "--dry-run")
    assert "sk-ds" not in result.output
    assert KEY not in result.output


def test_dsh_invalid_patch_fails_before_writing(api) -> None:
    dsh.patch_path("web").parent.mkdir(parents=True)
    dsh.patch_path("web").write_text("- id: x\n  config: [unclosed\n")
    result = CliRunner().invoke(setup, ["dsh"])
    assert result.exit_code == 1
    assert "Couldn't read DeepSeek Harness's config" in result.output
    assert not dsh.credentials_path().exists()


def test_setup_needs_the_key_in_the_environment(tool_homes: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIGHTNING_API_KEY", raising=False)
    result = CliRunner().invoke(setup, ["dsh"])
    assert result.exit_code == 1
    assert "Set LIGHTNING_API_KEY" in result.output
    assert not dsh.credentials_path().exists()


# Cursor


def test_cursor_prints_the_key_and_steps(api) -> None:
    result = invoke(setup, "cursor")

    assert result.exit_code == 0
    assert KEY in result.output
    assert "Override OpenAI Base URL" in result.output
    assert "https://code.lightning.ai/v1" in result.output
    for model_id in ("lightning-ai/glm-5.3", "lightning-ai/glm-5.3-flash", "lightning-ai/deepseek-v4.1-flash"):
        assert model_id in result.output
    assert _records()["cursor"] == {"managed": True}


def test_cursor_remove_explains_and_forgets_the_mark(api) -> None:
    assert invoke(setup, "cursor").exit_code == 0
    result = invoke(remove, "cursor")
    assert "Override OpenAI Base URL" in result.output
    assert "cursor" not in _records()
    assert "isn't set up" in invoke(remove, "cursor").output


# all of them


def test_status_lists_every_tool(api) -> None:
    for tool in ("pi", "codex", "dsh"):
        assert invoke(setup, tool).exit_code == 0
    infos = {info["tool"]: info for info in json.loads(invoke(status, "--json").output)}

    assert set(infos) == {"opencode", "pi", "codex", "dsh", "cursor"}
    assert [infos[t]["managed"] for t in ("pi", "codex", "dsh")] == [True, True, True]
    assert infos["opencode"]["configured"] is False
    assert "DeepSeek Harness: set up by `lightning code`" in invoke(status).output
    assert KEY not in invoke(status, "--json").output


EXAMPLES = Path(__file__).parents[3] / "examples" / "code"


@pytest.mark.parametrize(
    ("tool_id", "file_name", "example"),
    [
        ("pi", "models.json", "pi-models.json"),
        ("pi", "settings.json", "pi-settings.json"),
        ("codex", "lightning.config.toml", "codex-lightning.config.toml"),
        ("dsh", "cordis.patch.yml", "dsh-cordis.patch.yml"),
        ("dsh", ".credentials.yaml", "dsh-credentials.yaml"),
    ],
)
def test_examples_match_what_setup_writes(tool_id: str, file_name: str, example: str) -> None:
    from lightning_sdk.cli.code.models import FALLBACK_MODELS
    from lightning_sdk.cli.code.registry import TOOLS

    tool = TOOLS[tool_id]
    plan = tool.plan_setup(tool.read(), models=FALLBACK_MODELS, model=None, key="sk-lit-replace-me")
    change = next(change for change in plan.changes if change.path.name == file_name)
    assert change.after == (EXAMPLES / example).read_text()
