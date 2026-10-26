import json
import stat
from pathlib import Path

import pytest
from click.testing import CliRunner

from lightning_sdk.cli.code import opencode
from lightning_sdk.cli.code import models as coding_models
from lightning_sdk.cli.code.models import DEFAULT_MODEL, FALLBACK_MODELS
from lightning_sdk.cli.code.remove import remove
from lightning_sdk.cli.code.setup import setup
from lightning_sdk.cli.code.status import status
from lightning_sdk.utils import jsonc
from tests.cli.code.conftest import KEY, invoke
from tests.cli.help import assert_help_contains, mock_command_logging

USER_CONFIG = """{
  "$schema": "https://opencode.ai/config.json",
  // keep this comment
  "theme": "tokyonight",
  "model": "anthropic/claude-sonnet-5-5"
}
"""


def _auth() -> dict:
    return json.loads(opencode.auth_path().read_text())


def _config_path() -> Path:
    return opencode.config_dir() / "opencode.json"


@mock_command_logging
def test_code_help() -> None:
    assert_help_contains("lightning code --help", "Usage: lightning code", "Coding agents on code.lightning.ai.")
    assert_help_contains("lightning code setup --help", "Usage: lightning code setup", "--model", "--dry-run")


def test_code_token_is_gone() -> None:
    from lightning_sdk.cli.groups import code

    assert "token" not in code.commands
    assert set(code.commands) == {"setup", "status", "remove"}


def test_setup_creates_config_and_writes_the_env_key(api) -> None:
    result = invoke(setup, "opencode")
    assert result.exit_code == 0, result.output

    config = jsonc.loads(_config_path().read_text())
    assert config["$schema"] == opencode.SCHEMA_URL
    assert config["model"] == "lightning/deepseek-v4.1-flash"
    provider = config["provider"]["lightning"]
    assert provider["options"]["baseURL"] == "https://code.lightning.ai/v1"
    assert "apiKey" not in provider["options"]
    assert set(provider["models"]) == {"glm-5.3", "glm-5.3-flash", "deepseek-v4.1-flash"}

    entry = _auth()["lightning"]
    assert entry["type"] == "api"
    assert entry["key"] == KEY
    assert entry["metadata"] == {"managed_by": "lightning-sdk"}
    assert stat.S_IMODE(opencode.auth_path().stat().st_mode) == 0o600


def test_setup_keeps_the_rest_of_the_users_files(api) -> None:
    _config_path().parent.mkdir(parents=True)
    _config_path().write_text(USER_CONFIG)
    opencode.auth_path().parent.mkdir(parents=True)
    opencode.auth_path().write_text(json.dumps({"anthropic": {"type": "api", "key": "sk-ant"}}))

    assert invoke(setup, "opencode").exit_code == 0

    text = _config_path().read_text()
    assert "// keep this comment" in text
    assert jsonc.remove_value(text, ["provider"]) == USER_CONFIG
    # the user's own default model stays
    assert jsonc.loads(text)["model"] == "anthropic/claude-sonnet-5-5"
    assert _auth()["anthropic"] == {"type": "api", "key": "sk-ant"}
    assert (opencode.config_dir() / "opencode.json.lightning-backup").read_text() == USER_CONFIG


def test_setup_prefers_the_jsonc_file(api) -> None:
    opencode.config_dir().mkdir(parents=True)
    (opencode.config_dir() / "opencode.json").write_text("{}")
    (opencode.config_dir() / "opencode.jsonc").write_text("{\n  // mine\n}\n")

    assert invoke(setup, "opencode").exit_code == 0
    assert "lightning" in jsonc.loads((opencode.config_dir() / "opencode.jsonc").read_text())["provider"]
    assert (opencode.config_dir() / "opencode.json").read_text() == "{}"


def test_setup_with_model_sets_the_default(api) -> None:
    _config_path().parent.mkdir(parents=True)
    _config_path().write_text(USER_CONFIG)

    assert invoke(setup, "opencode", "--model", "glm-5.3-flash").exit_code == 0
    assert jsonc.loads(_config_path().read_text())["model"] == "lightning/glm-5.3-flash"


def test_setup_rerun_writes_the_key_from_the_environment_again(api, monkeypatch: pytest.MonkeyPatch) -> None:
    assert invoke(setup, "opencode").exit_code == 0
    monkeypatch.setenv("LIGHTNING_API_KEY", "lit_sa_rotated")
    assert invoke(setup, "opencode").exit_code == 0
    assert _auth()["lightning"]["key"] == "lit_sa_rotated"


def test_setup_will_not_replace_a_hand_made_provider_without_force(api) -> None:
    _config_path().parent.mkdir(parents=True)
    _config_path().write_text('{"provider": {"lightning": {"options": {"apiKey": "sk-lit-old"}}}}')

    result = CliRunner().invoke(setup, ["opencode"])
    assert result.exit_code == 1
    assert "--force" in result.output

    assert invoke(setup, "opencode", "--force").exit_code == 0
    assert "apiKey" not in jsonc.loads(_config_path().read_text())["provider"]["lightning"]["options"]


def test_setup_dry_run_writes_nothing(api) -> None:
    result = invoke(setup, "opencode", "--dry-run")

    assert result.exit_code == 0
    assert '+    "lightning": {' in result.output
    assert KEY not in result.output
    assert not _config_path().exists()
    assert not opencode.auth_path().exists()


def test_setup_needs_the_key_in_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIGHTNING_API_KEY", raising=False)
    result = CliRunner().invoke(setup, ["opencode"])
    assert result.exit_code == 1
    assert "Set LIGHTNING_API_KEY" in result.output
    assert not _config_path().exists()


def test_setup_invalid_config_fails_before_writing(api) -> None:
    _config_path().parent.mkdir(parents=True)
    _config_path().write_text('{"theme": }')

    result = CliRunner().invoke(setup, ["opencode"])
    assert result.exit_code == 1
    assert "Couldn't read OpenCode's config" in result.output
    assert _config_path().read_text() == '{"theme": }'


def test_status_and_remove(api) -> None:
    _config_path().parent.mkdir(parents=True)
    _config_path().write_text("{\n  // keep this comment\n}\n")
    assert invoke(setup, "opencode").exit_code == 0

    result = invoke(status, "--json")
    info = next(entry for entry in json.loads(result.output) if entry["tool"] == "opencode")
    assert info["configured"] is True
    assert info["managed"] is True
    assert info["model"] == "lightning/deepseek-v4.1-flash"
    assert "org" not in info
    assert KEY not in result.output

    result = invoke(remove, "opencode")
    assert result.exit_code == 0
    assert _config_path().read_text() == "{\n  // keep this comment\n}\n"
    assert "lightning" not in _auth()

    assert "isn't set up" in invoke(remove, "opencode").output
    assert "OpenCode: not set up" in invoke(status).output


def test_remove_takes_out_a_lightning_default_the_user_set(api) -> None:
    _config_path().parent.mkdir(parents=True)
    _config_path().write_text('{"provider": {"lightning": {}}, "model": "lightning/glm-5.3", "theme": "x"}')
    assert invoke(setup, "opencode", "--force").exit_code == 0

    assert invoke(remove, "opencode").exit_code == 0
    assert jsonc.loads(_config_path().read_text()) == {"theme": "x"}


def test_remove_keeps_a_default_model_the_user_changed(api) -> None:
    assert invoke(setup, "opencode").exit_code == 0
    _config_path().write_text(jsonc.set_value(_config_path().read_text(), ["model"], "anthropic/claude"))

    assert invoke(remove, "opencode").exit_code == 0
    assert jsonc.loads(_config_path().read_text()) == {
        "$schema": opencode.SCHEMA_URL,
        "model": "anthropic/claude",
    }


def test_warnings_point_at_overrides(tool_homes: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENCODE_AUTH_CONTENT", "{}")
    _config_path().parent.mkdir(parents=True)
    _config_path().write_text('{"enabled_providers": ["anthropic"], "disabled_providers": ["lightning"]}')
    project = tool_homes / "repo"
    (project / ".git").mkdir(parents=True)
    (project / "opencode.json").write_text('{"model": "anthropic/claude"}')

    tool = opencode.OpenCode()
    notes = tool.warnings(tool.read(), cwd=project)

    assert any("OPENCODE_AUTH_CONTENT" in note for note in notes)
    assert any("disabled_providers" in note for note in notes)
    assert any("sets model to anthropic/claude" in note for note in notes)


def test_example_config_matches_what_setup_writes() -> None:
    example = Path(__file__).parents[3] / "examples" / "code" / "opencode.json"
    tool = opencode.OpenCode()
    plan = tool.plan_setup(tool.read(), models=FALLBACK_MODELS, model=None, key="sk-lit-1")
    config = next(change for change in plan.changes if change.path == _config_path())
    assert config.after == example.read_text()


def test_default_model_is_one_setup_configures() -> None:
    assert DEFAULT_MODEL == "deepseek-v4.1-flash"
    assert DEFAULT_MODEL in opencode.provider_config(FALLBACK_MODELS)["models"]
    assert DEFAULT_MODEL in opencode.provider_config(coding_models.fetch_models())["models"]


def test_fetch_models_reads_the_openrouter_fields(models_api) -> None:
    models = {model.key: model for model in coding_models.fetch_models()}

    models_api.assert_called_once_with("https://code.lightning.ai/v1/models", timeout=10)
    assert models["deepseek-v4.1-flash"] == coding_models.CodingModel(
        key="deepseek-v4.1-flash",
        id="lightning-ai/deepseek-v4.1-flash",
        name="DeepSeek V4.1 Flash",
        context_window=253_952,
        output_tokens=131_072,
        images=True,
    )
    assert models["glm-5.3"].images is False
    assert models["glm-5.3"].context_window == 1_048_576


def test_fallback_matches_what_the_api_served() -> None:
    assert coding_models.fetch_models() == FALLBACK_MODELS


def test_fetch_models_skips_entries_it_cannot_configure(models_api) -> None:
    models_api.return_value.json.return_value = {
        "data": [
            {"id": "lightning-ai/no-limits"},
            {"object": "model"},
            {"id": "lightning-ai/new", "context_length": 1000, "top_provider": {"max_completion_tokens": 100}},
        ]
    }
    [model] = coding_models.fetch_models()
    assert (model.key, model.name, model.images, model.tools, model.reasoning) == (
        "new",
        "lightning-ai/new",
        False,
        True,
        True,
    )

    models_api.return_value.json.return_value = {"data": []}
    with pytest.raises(ValueError, match="no models"):
        coding_models.fetch_models()


def test_setup_writes_the_models_the_api_lists(api, models_api) -> None:
    models_api.return_value.json.return_value = {
        "data": [
            {
                "id": "lightning-ai/next-model",
                "name": "Next Model",
                "context_length": 500_000,
                "architecture": {"input_modalities": ["text"]},
                "top_provider": {"max_completion_tokens": 65_536},
                "supported_parameters": ["max_tokens"],
            }
        ]
    }
    assert invoke(setup, "opencode").exit_code == 0

    config = jsonc.loads(_config_path().read_text())
    assert config["provider"]["lightning"]["models"] == {
        "next-model": {
            "id": "lightning-ai/next-model",
            "name": "Next Model",
            "reasoning": False,
            "tool_call": False,
            "limit": {"context": 500_000, "output": 65_536},
        }
    }
    # the preferred default isn't served, so the first listed model is
    assert config["model"] == "lightning/next-model"


def test_setup_falls_back_to_the_built_in_models(api, models_api) -> None:
    models_api.side_effect = OSError("network down")
    result = invoke(setup, "opencode")

    assert result.exit_code == 0
    assert "using the built-in one" in result.output
    models = jsonc.loads(_config_path().read_text())["provider"]["lightning"]["models"]
    assert set(models) == {model.key for model in FALLBACK_MODELS}


def test_setup_rejects_an_unknown_model(api) -> None:
    result = CliRunner().invoke(setup, ["opencode", "--model", "gpt-9"])
    assert result.exit_code == 2
    assert "Unknown model 'gpt-9'" in result.output


def test_setup_replaces_a_default_on_a_retired_model(api) -> None:
    _config_path().parent.mkdir(parents=True)
    _config_path().write_text('{"model": "lightning/glm-4"}')
    assert invoke(setup, "opencode").exit_code == 0
    assert jsonc.loads(_config_path().read_text())["model"] == "lightning/deepseek-v4.1-flash"
