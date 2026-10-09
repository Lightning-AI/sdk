import json
import stat
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner, Result

from lightning_sdk.cli.code import account, opencode
from lightning_sdk.cli.code.models import DEFAULT_MODEL
from lightning_sdk.cli.code.remove import remove
from lightning_sdk.cli.code.setup import setup
from lightning_sdk.cli.code.status import status
from lightning_sdk.cli.code.token import token
from lightning_sdk.utils import jsonc
from tests.cli.help import assert_help_contains, mock_command_logging

USER_CONFIG = """{
  "$schema": "https://opencode.ai/config.json",
  // keep this comment
  "theme": "tokyonight",
  "model": "anthropic/claude-sonnet-5-5"
}
"""


@pytest.fixture(autouse=True)
def opencode_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in ("OPENCODE_CONFIG", "OPENCODE_CONFIG_CONTENT", "OPENCODE_AUTH_CONTENT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _org(plan="Enterprise", name="my-org", org_id="org-1", **kwargs) -> account.CodingOrg:
    fields = {"display_name": "", "personal": False, "coding_disabled": False, **kwargs}
    return account.CodingOrg(id=org_id, name=name, plan=plan, **fields)


@pytest.fixture()
def api():
    """Mock everything that talks to Lightning: org choice, key creation and revocation."""
    keys = iter(range(1, 100))

    def create_key(org, name, description):
        n = next(keys)
        return SimpleNamespace(id=f"key-{n}", name=name, raw_key=f"sk-lit-{n}")

    with patch.object(account, "choose_org", return_value=_org()) as choose, patch.object(
        account, "create_key", side_effect=create_key
    ) as create, patch.object(account, "key_exists", return_value=True) as exists, patch.object(
        account, "revoke_key", return_value=True
    ) as revoke:
        yield SimpleNamespace(choose_org=choose, create_key=create, key_exists=exists, revoke_key=revoke)


def _invoke(command: click.Command, *args: str) -> Result:
    with patch("lightning_sdk.cli.utils.logging._log_command", new=MagicMock()):
        return CliRunner().invoke(command, list(args), catch_exceptions=False)


def _auth() -> dict:
    return json.loads(opencode.auth_path().read_text())


def _config_path() -> Path:
    return opencode.config_dir() / "opencode.json"


@mock_command_logging
def test_code_help() -> None:
    assert_help_contains("lightning code --help", "Usage: lightning code", "Coding agents on code.lightning.ai.")
    assert_help_contains("lightning code setup --help", "Usage: lightning code setup", "--rotate-key")
    assert_help_contains("lightning code token --help", "Usage: lightning code token", "Create an API key")


def test_setup_creates_config_and_key(api) -> None:
    result = _invoke(setup, "opencode", "--org", "my-org")
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
    assert entry["key"] == "sk-lit-1"
    assert entry["metadata"] == {
        "managed_by": "lightning-sdk",
        "org_id": "org-1",
        "org_name": "my-org",
        "key_id": "key-1",
        "key_name": api.create_key.call_args.args[1],
    }
    assert stat.S_IMODE(opencode.auth_path().stat().st_mode) == 0o600
    api.choose_org.assert_called_once_with("my-org", previous_org_id=None)


def test_setup_keeps_the_rest_of_the_users_files(api) -> None:
    _config_path().parent.mkdir(parents=True)
    _config_path().write_text(USER_CONFIG)
    opencode.auth_path().parent.mkdir(parents=True)
    opencode.auth_path().write_text(json.dumps({"anthropic": {"type": "api", "key": "sk-ant"}}))

    assert _invoke(setup, "opencode", "--org", "my-org").exit_code == 0

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

    assert _invoke(setup, "opencode", "--org", "my-org").exit_code == 0
    assert "lightning" in jsonc.loads((opencode.config_dir() / "opencode.jsonc").read_text())["provider"]
    assert (opencode.config_dir() / "opencode.json").read_text() == "{}"


def test_setup_with_model_sets_the_default(api) -> None:
    _config_path().parent.mkdir(parents=True)
    _config_path().write_text(USER_CONFIG)

    assert _invoke(setup, "opencode", "--org", "my-org", "--model", "glm-5.3-flash").exit_code == 0
    assert jsonc.loads(_config_path().read_text())["model"] == "lightning/glm-5.3-flash"


def test_setup_rerun_reuses_the_key(api) -> None:
    assert _invoke(setup, "opencode", "--org", "my-org").exit_code == 0
    assert _invoke(setup, "opencode", "--org", "my-org").exit_code == 0

    assert api.create_key.call_count == 1
    assert _auth()["lightning"]["key"] == "sk-lit-1"
    api.choose_org.assert_called_with("my-org", previous_org_id="org-1")
    api.revoke_key.assert_not_called()


def test_setup_rotate_key_revokes_the_old_one(api) -> None:
    assert _invoke(setup, "opencode", "--org", "my-org").exit_code == 0
    result = _invoke(setup, "opencode", "--org", "my-org", "--rotate-key")

    assert result.exit_code == 0
    assert _auth()["lightning"]["key"] == "sk-lit-2"
    api.revoke_key.assert_called_once_with("org-1", "key-1")
    assert "Revoked the previous API key" in result.output


def test_setup_switching_org_creates_a_key_there(api) -> None:
    assert _invoke(setup, "opencode", "--org", "my-org").exit_code == 0
    api.choose_org.return_value = _org(name="other", org_id="org-2")
    assert _invoke(setup, "opencode", "--org", "other").exit_code == 0

    assert _auth()["lightning"]["metadata"]["org_id"] == "org-2"
    api.revoke_key.assert_called_once_with("org-1", "key-1")


def test_setup_replaces_a_deleted_key(api) -> None:
    assert _invoke(setup, "opencode", "--org", "my-org").exit_code == 0
    api.key_exists.return_value = False
    assert _invoke(setup, "opencode", "--org", "my-org").exit_code == 0
    assert _auth()["lightning"]["key"] == "sk-lit-2"


def test_setup_free_plan_asks_to_upgrade(api) -> None:
    api.choose_org.return_value = _org(plan="Free")
    with patch.object(account, "_get_cloud_url", return_value="https://lightning.ai"):
        result = CliRunner().invoke(setup, ["opencode", "--org", "my-org"])

    assert result.exit_code == 1
    assert "Free plan" in result.output
    assert "https://lightning.ai/me/settings/coding-usage?coding_org=org-1" in result.output
    api.create_key.assert_not_called()
    assert not _config_path().exists()


def test_setup_coding_disabled_org_is_refused(api) -> None:
    api.choose_org.return_value = _org(coding_disabled=True)
    result = CliRunner().invoke(setup, ["opencode", "--org", "my-org"])
    assert result.exit_code == 1
    assert "turned off" in result.output
    api.create_key.assert_not_called()


def test_setup_will_not_replace_a_hand_made_provider_without_force(api) -> None:
    _config_path().parent.mkdir(parents=True)
    _config_path().write_text('{"provider": {"lightning": {"options": {"apiKey": "sk-lit-old"}}}}')

    result = CliRunner().invoke(setup, ["opencode", "--org", "my-org"])
    assert result.exit_code == 1
    assert "--force" in result.output
    api.create_key.assert_not_called()

    assert _invoke(setup, "opencode", "--org", "my-org", "--force").exit_code == 0
    assert "apiKey" not in jsonc.loads(_config_path().read_text())["provider"]["lightning"]["options"]


def test_setup_dry_run_writes_nothing(api) -> None:
    result = _invoke(setup, "opencode", "--org", "my-org", "--dry-run")

    assert result.exit_code == 0
    assert '+    "lightning": {' in result.output
    assert "Would create an API key" in result.output
    assert not _config_path().exists()
    assert not opencode.auth_path().exists()
    api.create_key.assert_not_called()


def test_setup_invalid_config_fails_before_creating_a_key(api) -> None:
    _config_path().parent.mkdir(parents=True)
    _config_path().write_text('{"theme": }')

    result = CliRunner().invoke(setup, ["opencode", "--org", "my-org"])
    assert result.exit_code == 1
    assert "Couldn't read OpenCode's config" in result.output
    api.create_key.assert_not_called()


def test_setup_revokes_the_new_key_when_writing_fails(api) -> None:
    with patch.object(opencode, "apply_setup", side_effect=OSError("disk full")), pytest.raises(
        OSError, match="disk full"
    ):
        _invoke(setup, "opencode", "--org", "my-org")
    api.revoke_key.assert_called_once_with("org-1", "key-1")


def test_status_and_remove(api) -> None:
    _config_path().parent.mkdir(parents=True)
    _config_path().write_text("{\n  // keep this comment\n}\n")
    assert _invoke(setup, "opencode", "--org", "my-org").exit_code == 0

    result = _invoke(status, "--json")
    [info] = json.loads(result.output)
    assert info["configured"] is True
    assert info["managed"] is True
    assert info["org"] == "my-org"
    assert info["key_id"] == "key-1"
    assert info["model"] == "lightning/deepseek-v4.1-flash"

    result = _invoke(remove, "opencode")
    assert result.exit_code == 0
    assert "Revoked the API key" in result.output
    api.revoke_key.assert_called_once_with("org-1", "key-1")
    assert _config_path().read_text() == "{\n  // keep this comment\n}\n"
    assert "lightning" not in _auth()

    assert "isn't set up" in _invoke(remove, "opencode").output
    assert "Not set up" in _invoke(status).output


def test_remove_takes_out_a_lightning_default_the_user_set(api) -> None:
    _config_path().parent.mkdir(parents=True)
    _config_path().write_text('{"provider": {"lightning": {}}, "model": "lightning/glm-5.3", "theme": "x"}')
    assert _invoke(setup, "opencode", "--org", "my-org", "--force").exit_code == 0

    assert _invoke(remove, "opencode").exit_code == 0
    assert jsonc.loads(_config_path().read_text()) == {"theme": "x"}


def test_remove_keeps_a_default_model_the_user_changed(api) -> None:
    assert _invoke(setup, "opencode", "--org", "my-org").exit_code == 0
    _config_path().write_text(jsonc.set_value(_config_path().read_text(), ["model"], "anthropic/claude"))

    assert _invoke(remove, "opencode", "--keep-key").exit_code == 0
    assert jsonc.loads(_config_path().read_text()) == {
        "$schema": opencode.SCHEMA_URL,
        "model": "anthropic/claude",
    }
    api.revoke_key.assert_not_called()


def test_warnings_point_at_overrides(opencode_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENCODE_AUTH_CONTENT", "{}")
    _config_path().parent.mkdir(parents=True)
    _config_path().write_text('{"enabled_providers": ["anthropic"], "disabled_providers": ["lightning"]}')
    project = opencode_home / "repo"
    (project / ".git").mkdir(parents=True)
    (project / "opencode.json").write_text('{"model": "anthropic/claude"}')

    notes = opencode.warnings(opencode.read_state(), cwd=project)

    assert any("OPENCODE_AUTH_CONTENT" in note for note in notes)
    assert any("enabled_providers" in note for note in notes)
    assert any("disabled_providers" in note for note in notes)
    assert any("sets model to anthropic/claude" in note for note in notes)


def test_token_prints_a_new_key(api) -> None:
    result = _invoke(token, "--org", "my-org")
    assert result.exit_code == 0
    assert result.output == "sk-lit-1\n"

    result = _invoke(token, "--org", "my-org", "--name", "ci", "--json")
    assert json.loads(result.output) == {
        "api_key": "sk-lit-2",
        "base_url": "https://code.lightning.ai/v1",
        "key_id": "key-2",
        "key_name": "ci",
        "org": "my-org",
        "org_id": "org-1",
    }


def test_token_free_plan_asks_to_upgrade(api) -> None:
    api.choose_org.return_value = _org(plan="Free")
    result = CliRunner().invoke(token, ["--org", "my-org"])
    assert result.exit_code == 1
    assert "Upgrade to Pro or Teams" in result.output
    api.create_key.assert_not_called()


def _v1_org(name: str, org_id: str, personal: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        id=org_id, name=name, display_name=name.title(), is_personal_org=personal, disable_coding_agents=False
    )


@pytest.fixture()
def client(inline_executor_cls):
    client = MagicMock()
    client.organizations_service_list_organizations.return_value.organizations = [
        _v1_org("zeta", "org-z"),
        _v1_org("alpha", "org-a"),
        _v1_org("me", "org-me", personal=True),
    ]
    plans = {"org-z": "Teams", "org-a": "Free", "org-me": "Professional"}
    client.billing_service_get_billing_subscription.side_effect = lambda org_id: SimpleNamespace(name=plans[org_id])
    with patch.object(account, "cached_lightning_client", return_value=client), patch.object(
        account, "ThreadPoolExecutor", inline_executor_cls
    ):
        yield client


def test_choose_org_by_name_reads_only_that_plan(client) -> None:
    org = account.choose_org("zeta")
    assert (org.id, org.plan, org.tier) == ("org-z", "Teams", "teams")
    client.billing_service_get_billing_subscription.assert_called_once_with(org_id="org-z")


def test_choose_org_needs_org_without_a_terminal(client) -> None:
    with patch.object(account, "_interactive", return_value=False), pytest.raises(click.UsageError, match="--org"):
        account.choose_org(None)


def test_choose_org_asks_with_paid_orgs_preselected(client) -> None:
    with patch.object(account, "_interactive", return_value=True), patch.object(
        account.click, "prompt", return_value=3
    ) as prompt, patch.object(account.click, "echo") as echo:
        org = account.choose_org(None)

    shown = [call.args[0] for call in echo.call_args_list]
    assert shown[1:] == [
        "  1. Me (personal)  (Professional)",
        "  2. Alpha  (Free, upgrade needed)",
        "  3. Zeta  (Teams)",
    ]
    assert prompt.call_args.kwargs["default"] == 1
    assert org.id == "org-z"


def test_choose_org_unknown_name(client) -> None:
    with pytest.raises(click.UsageError, match="alpha, zeta"):
        account.choose_org("nope")


def test_unreadable_plan_is_allowed_with_a_note() -> None:
    with patch.object(account.click, "echo") as echo:
        account.require_coding_plan(_org(plan=None))
    assert "Couldn't read the plan" in echo.call_args.args[0]


def test_example_config_matches_what_setup_writes() -> None:
    example = Path(__file__).parents[3] / "examples" / "code" / "opencode.json"
    plan = opencode.plan_setup(opencode.read_state(), model=None)
    assert plan.config_text == example.read_text()


def test_default_model_is_one_setup_configures() -> None:
    assert DEFAULT_MODEL == "deepseek-v4.1-flash"
    assert DEFAULT_MODEL in opencode.provider_config()["models"]
