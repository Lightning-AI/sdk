import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner, Result

from lightning_sdk.cli.code import account
from lightning_sdk.cli.code import models as coding_models


@pytest.fixture(autouse=True)
def tool_homes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every coding tool's config, and the home directory, into the test's own folder."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("PI_CODING_AGENT_DIR", str(tmp_path / "pi"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    monkeypatch.setenv("DSH_HOME", str(tmp_path / "dsh"))
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in ("OPENCODE_CONFIG", "OPENCODE_CONFIG_CONTENT", "OPENCODE_AUTH_CONTENT", "LIGHTNING_CODE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


MODELS_RESPONSE = json.loads((Path(__file__).parent / "models_response.json").read_text())


@pytest.fixture(autouse=True)
def models_api():
    """Serve /v1/models from a copy of what code.lightning.ai returned, instead of the network."""
    response = MagicMock()
    response.json.return_value = MODELS_RESPONSE
    with patch.object(coding_models.requests, "get", return_value=response) as get:
        yield get


def make_org(plan="Enterprise", name="my-org", org_id="org-1", **kwargs) -> account.CodingOrg:
    fields = {"display_name": "", "personal": False, "coding_disabled": False, **kwargs}
    return account.CodingOrg(id=org_id, name=name, plan=plan, **fields)


@pytest.fixture()
def api():
    """Mock everything that talks to Lightning: org choice, key creation and revocation."""
    keys = iter(range(1, 100))

    def create_key(org, name, description):
        n = next(keys)
        return SimpleNamespace(id=f"key-{n}", name=name, raw_key=f"sk-lit-{n}")

    with patch.object(account, "choose_org", return_value=make_org()) as choose, patch.object(
        account, "create_key", side_effect=create_key
    ) as create, patch.object(account, "key_exists", return_value=True) as exists, patch.object(
        account, "revoke_key", return_value=True
    ) as revoke:
        yield SimpleNamespace(choose_org=choose, create_key=create, key_exists=exists, revoke_key=revoke)


def invoke(command: click.Command, *args: str) -> Result:
    with patch("lightning_sdk.cli.utils.logging._log_command", new=MagicMock()):
        return CliRunner().invoke(command, list(args), catch_exceptions=False)
