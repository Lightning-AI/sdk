from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from lightning_sdk.api.deployment_api import ApiKeyAuth, Env, TokenAuth
from lightning_sdk.cli.deployment import common
from lightning_sdk.cli.deployment.common import parse_auth, parse_env
from lightning_sdk.lightning_cloud.openapi import V1AuthType


def _as_tuples(entries):
    return [
        ("literal", e.name, e.value) if isinstance(e, Env) else ("secret", e.name, e.env_name) for e in (entries or [])
    ]


def test_parse_env_returns_none_when_empty():
    assert parse_env([""], []) is None


def test_parse_env_parses_literals_and_secrets():
    entries = parse_env(["KEY=value"], ["TOKEN"])
    assert _as_tuples(entries) == [("literal", "KEY", "value"), ("secret", "TOKEN", None)]


def test_parse_env_parses_secret_alias():
    # ENV_NAME=secret_name injects the secret under a different env var name.
    entries = parse_env([""], ["ENV_ALIAS=source_secret"])
    assert _as_tuples(entries) == [("secret", "source_secret", "ENV_ALIAS")]


@contextmanager
def _patch_whoami(auth_type=V1AuthType.USER, side_effect=None):
    with patch.object(common, "AuthApi") as mock:
        if side_effect is not None:
            mock.return_value.whoami.side_effect = side_effect
        else:
            mock.return_value.whoami.return_value = SimpleNamespace(auth_type=auth_type)
        yield mock


def test_parse_auth_warns_when_a_scoped_key_picks_api_key_auth(capsys):
    # --api-key-auth gates on a user key, so the caller's own scoped key gets 401.
    with _patch_whoami(auth_type=V1AuthType.SCOPED_API_KEY):
        auth = parse_auth(api_key_auth=True)

    assert isinstance(auth, ApiKeyAuth)
    err = capsys.readouterr().err
    assert "scoped API key" in err
    assert "--token-auth" in err


def test_parse_auth_is_quiet_for_a_user_key(capsys):
    with _patch_whoami(auth_type=V1AuthType.USER):
        auth = parse_auth(api_key_auth=True)

    assert isinstance(auth, ApiKeyAuth)
    assert capsys.readouterr().err == ""


def test_parse_auth_survives_a_failing_identity_lookup(capsys):
    # The warning is advisory; a whoami failure must not block the deployment.
    with _patch_whoami(side_effect=RuntimeError("boom")):
        auth = parse_auth(api_key_auth=True)

    assert isinstance(auth, ApiKeyAuth)
    assert capsys.readouterr().err == ""


def test_parse_auth_does_not_look_up_identity_for_token_auth():
    with _patch_whoami(auth_type=V1AuthType.SCOPED_API_KEY) as mock:
        auth = parse_auth(token_auth="secret")

    assert isinstance(auth, TokenAuth)
    mock.assert_not_called()
