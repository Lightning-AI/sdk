"""require_auth_header reads the credential source and nothing patches the vendored login."""

import click
import pytest

from lightning_sdk.cli.utils.auth import require_auth_header
from lightning_sdk.lightning_cloud.login import Auth, AuthServer


def test_require_auth_header_returns_the_environment_token(monkeypatch) -> None:
    monkeypatch.setenv("LIGHTNING_AUTH_TOKEN", "env-token")

    assert require_auth_header() == "Bearer env-token"


def test_require_auth_header_turns_a_missing_credential_into_a_usage_error(monkeypatch) -> None:
    monkeypatch.delenv("LIGHTNING_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("LIGHTNING_API_KEY", raising=False)
    monkeypatch.delenv("LIGHTNING_AUTH_TOKEN_FILE", raising=False)
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda *_args, **_kwargs: opened.append(True))

    with pytest.raises(click.UsageError, match="lightning login"):
        require_auth_header()

    assert opened == []


def test_importing_the_cli_leaves_the_vendored_login_in_place() -> None:
    import lightning_sdk.api.llm_api
    import lightning_sdk.cli.entrypoint
    import lightning_sdk.cli.legacy.deploy._auth

    assert lightning_sdk.cli.entrypoint.main_cli is not None
    assert lightning_sdk.api.llm_api.authenticate is not None
    assert lightning_sdk.cli.legacy.deploy._auth.authenticate is not None
    assert Auth.save.__module__ == "lightning_sdk.lightning_cloud.login"
    assert AuthServer.login_with_browser.__module__ == "lightning_sdk.lightning_cloud.login"
