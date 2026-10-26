import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner, Result

from lightning_sdk.cli.code import models as coding_models

# the key `lightning code setup` reads from LIGHTNING_API_KEY, and writes into each tool's config
KEY = "lit_sa_test-key"


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
    monkeypatch.delenv("LIGHTNING_API_KEY", raising=False)
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


@pytest.fixture()
def api(monkeypatch: pytest.MonkeyPatch):
    """Put the key setup reads in LIGHTNING_API_KEY."""
    monkeypatch.setenv("LIGHTNING_API_KEY", KEY)
    return KEY


def invoke(command: click.Command, *args: str) -> Result:
    with patch("lightning_sdk.cli.utils.logging._log_command", new=MagicMock()):
        return CliRunner().invoke(command, list(args), catch_exceptions=False)
