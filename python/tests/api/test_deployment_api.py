from unittest.mock import MagicMock

from lightning_sdk.api.deployment_api import (
    ApiKeyAuth,
    BasicAuth,
    DeploymentApi,
    TokenAuth,
    V1EndpointAuth,
    restore_auth,
    to_endpoint_auth,
)
from lightning_sdk.lightning_cloud.openapi import V1BYOMSpec, V1Deployment, V1JobSpec


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


def test_create_deployment_threads_byom_spec_and_acks(monkeypatch):
    monkeypatch.setattr("lightning_sdk.api.deployment_api.LightningClient", MagicMock())
    api = DeploymentApi()
    byom = V1BYOMSpec(served_model_name="meta-llama/Llama-3-8B")
    deployment = V1Deployment(
        name="d1",
        project_id="p1",
        spec=V1JobSpec(cluster_id="c1"),
        byom_spec=byom,
        acknowledged_warnings=["BYOM_INSUFFICIENT_VRAM_ESTIMATE"],
    )

    api.create_deployment(deployment)

    body = api._client.jobs_service_create_deployment.call_args.kwargs["body"]
    assert body.byom_spec is byom
    assert body.acknowledged_warnings == ["BYOM_INSUFFICIENT_VRAM_ESTIMATE"]
