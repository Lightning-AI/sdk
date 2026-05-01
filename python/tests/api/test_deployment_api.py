from lightning_sdk.api.deployment_api import (
    ApiKeyAuth,
    BasicAuth,
    TokenAuth,
    V1EndpointAuth,
    restore_auth,
    to_endpoint_auth,
)


def test_auth_to_proto_and_restore():
    def fn(x):
        return restore_auth(to_endpoint_auth(x))

    assert isinstance(fn(ApiKeyAuth()), ApiKeyAuth)

    new = fn(BasicAuth(username="x", password="x"))
    assert isinstance(new, BasicAuth)
    assert new.username == "x"
    assert new.password == "x"

    new = fn(TokenAuth(token="x"))
    assert isinstance(new, TokenAuth)
    assert new.token == "x"


def test_restore_auth():
    assert isinstance(restore_auth(V1EndpointAuth(enabled=True, user_api_key=True)), ApiKeyAuth)

    new = restore_auth(V1EndpointAuth(enabled=True, username="x", password="x"))
    assert isinstance(new, BasicAuth)
    assert new.username == "x"
    assert new.password == "x"

    new = restore_auth(V1EndpointAuth(enabled=True, token="x"))
    assert isinstance(new, TokenAuth)
    assert new.token == "x"
