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
from lightning_sdk.lightning_cloud.openapi import (
    V1BYOMSpec,
    V1Deployment,
    V1DownloadJobLogsResponse,
    V1JobLogsResponse,
    V1JobSpec,
)
from lightning_sdk.lightning_cloud.openapi.rest import ApiException


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
    monkeypatch.setattr("lightning_sdk.api.utils.LightningClient", MagicMock())
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


def test_get_job_logs_falls_back_to_download_for_deployment_without_legacy_pages():
    api = object.__new__(DeploymentApi)
    api._client = MagicMock()
    api._client.jobs_service_get_job_logs.return_value = V1JobLogsResponse(follow_url="", pages=[])
    api._client.jobs_service_download_job_logs.return_value = V1DownloadJobLogsResponse(
        url="https://logs.example/deployment.log"
    )

    logs = api.get_job_logs("teamspace-id", "job-id", deployment_id="deployment-id")

    assert len(logs.pages) == 1
    assert logs.pages[0].url == "https://logs.example/deployment.log"
    api._client.jobs_service_download_job_logs.assert_called_once_with(
        project_id="teamspace-id",
        id="job-id",
        deployment_id="deployment-id",
        rank=0,
        cloudspace_id="",
    )


def test_get_job_logs_keeps_legacy_pages_when_available():
    api = object.__new__(DeploymentApi)
    api._client = MagicMock()
    expected = V1JobLogsResponse(pages=[MagicMock(url="https://logs.example/page.log")])
    api._client.jobs_service_get_job_logs.return_value = expected

    logs = api.get_job_logs("teamspace-id", "job-id", deployment_id="deployment-id")

    assert logs is expected
    api._client.jobs_service_download_job_logs.assert_not_called()


def test_get_job_logs_keeps_empty_legacy_response_when_download_is_unavailable():
    api = object.__new__(DeploymentApi)
    api._client = MagicMock()
    expected = V1JobLogsResponse(follow_url="", pages=[])
    api._client.jobs_service_get_job_logs.return_value = expected
    api._client.jobs_service_download_job_logs.side_effect = ApiException(status=404)

    logs = api.get_job_logs("teamspace-id", "job-id", deployment_id="deployment-id")

    assert logs is expected
