import pytest
from click import UsageError

from lightning_sdk.api.deployment_api import BasicAuth, Env, TokenAuth
from lightning_sdk.cli.deployment.common import parse_auth, parse_env


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


def test_parse_auth_returns_token_auth():
    assert isinstance(parse_auth(token_auth="secret"), TokenAuth)


def test_parse_auth_returns_basic_auth():
    auth = parse_auth(basic_auth="user:pass")

    assert isinstance(auth, BasicAuth)
    assert auth.username == "user"
    assert auth.password == "pass"


def test_parse_auth_rejects_basic_and_token_together():
    with pytest.raises(UsageError, match="mutually exclusive"):
        parse_auth(basic_auth="user:pass", token_auth="secret")
