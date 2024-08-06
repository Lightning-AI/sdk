from lightning_sdk.deployment import deployment as deployment_module
from lightning_sdk.deployment.deployment import AutoScaleConfig
from lightning_sdk.api import deployment_api as deployment_api_module
import pytest
from unittest.mock import MagicMock
from lightning_sdk.machine import Machine
from lightning_sdk.lightning_cloud.openapi import (
    V1ListDeploymentsResponse,
    V1Deployment,
    V1JobSpec,
    V1Endpoint,
    V1AutoscalingSpec,
)


def test_to_autoscaling():
    with pytest.raises(ValueError, match="The autoscaling metric is required. Currently supported metrics are"):
        deployment_api_module.to_autoscaling(
            AutoScaleConfig(),
            None,
        )

    with pytest.raises(ValueError, match="The number of replicas should be positive."):
        deployment_api_module.to_autoscaling(
            AutoScaleConfig(max_replicas=-1),
            -1,
        )

    with pytest.raises(ValueError, match="The minimum number of replicas should be positive."):
        deployment_api_module.to_autoscaling(
            AutoScaleConfig(min_replicas=-1),
            None,
        )

    with pytest.raises(ValueError, match="The maximum number of replicas should be positive."):
        deployment_api_module.to_autoscaling(
            AutoScaleConfig(max_replicas=-1),
            None,
        )

    with pytest.raises(
        ValueError, match="The minimum number of replicas should be smaller or equal to the maximum number of replicas."
    ):
        deployment_api_module.to_autoscaling(
            AutoScaleConfig(max_replicas=1, min_replicas=2),
            None,
        )

    with pytest.raises(ValueError, match="The autoscaling threshold should be defined between 0 and 100."):
        deployment_api_module.to_autoscaling(
            AutoScaleConfig(max_replicas=2, min_replicas=2, metric="CPU"),
            replicas=1,
        )

    autoscaling = deployment_api_module.to_autoscaling(
        AutoScaleConfig(max_replicas=2, min_replicas=2, metric="CPU", threshold=100),
        replicas=1,
    )
    assert autoscaling.min_replicas == 2
    assert autoscaling.max_replicas == 2
    assert autoscaling.target_metric.name == "CPU"
    assert autoscaling.target_metric.target == "100"


def test_to_endpoint():
    with pytest.raises(ValueError, match="At least one port is required to reach your deployment."):
        deployment_api_module.to_endpoint([], None, None)

    with pytest.raises(ValueError, match="The token should be defined."):
        endpoint = deployment_api_module.to_endpoint([10], deployment_api_module.TokenAuth(token=""), "custom_domain")

    with pytest.raises(ValueError, match="The username should be defined."):
        endpoint = deployment_api_module.to_endpoint(
            [10], deployment_api_module.BasicAuth(username="", password=""), "custom_domain"
        )

    with pytest.raises(ValueError, match="The password should be defined."):
        endpoint = deployment_api_module.to_endpoint(
            [10], deployment_api_module.BasicAuth(username="username", password=""), "custom_domain"
        )

    endpoint = deployment_api_module.to_endpoint([10], None, None)
    assert endpoint.ports == ["10"]

    endpoint = deployment_api_module.to_endpoint(
        [10], deployment_api_module.BasicAuth(username="username", password="password"), "custom_domain"
    )
    assert endpoint.ports == ["10"]
    assert endpoint.auth.username == "username"
    assert endpoint.auth.password == "password"
    assert endpoint.auth.token is None
    assert endpoint.custom_domain == "custom_domain"

    endpoint = deployment_api_module.to_endpoint([10], deployment_api_module.TokenAuth(token="token"), "custom_domain")
    assert endpoint.ports == ["10"]
    assert endpoint.auth.username is None
    assert endpoint.auth.password is None
    assert endpoint.auth.token == "token"
    assert endpoint.custom_domain == "custom_domain"


def test_deployment_start_first_time(monkeypatch):
    with pytest.raises(TypeError, match=r"missing 1 required positional argument: 'name'"):
        deployment_module.Deployment()

    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))

    client = MagicMock()
    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    with pytest.raises(ValueError, match="An autoscaling config should be provided."):
        deployment = deployment_module.Deployment(name="ollama")
        deployment.start()

    deployment = deployment_module.Deployment(name="ollama")
    deployment.start(
        autoscale=AutoScaleConfig(
            metric="GPU",
            threshold=75,
        ),
        ports=[50],
        cluster="cluster_id",
        machine=Machine.A10G,
        environment="ollama/ollama:latest",
    )
    client.jobs_service_create_deployment.assert_called()

    with pytest.raises(RuntimeError, match="This deployment has already been started."):
        deployment.start()


def test_deployment_start_already_exist(monkeypatch):
    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))

    client = MagicMock()
    client.jobs_service_list_deployments.return_value = V1ListDeploymentsResponse(
        deployments=[
            V1Deployment(
                name="ollama",
            )
        ]
    )
    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    deployment = deployment_module.Deployment(name="ollama")
    with pytest.raises(RuntimeError, match="This deployment has already been started."):
        deployment.start()


def test_deployment_update(monkeypatch):
    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))

    client = MagicMock()
    client.jobs_service_list_deployments.return_value = V1ListDeploymentsResponse(
        deployments=[
            V1Deployment(
                name="ollama",
                spec=V1JobSpec(),
                endpoint=V1Endpoint(),
                strategy=None,
            )
        ]
    )
    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    deployment = deployment_module.Deployment(name="ollama")

    with pytest.raises(RuntimeError, match="When doing a new release, a release strategy needs to be defined."):
        deployment.update(entrypoint="new_entrypoint")

    deployment.update(
        entrypoint="new_entrypoint", release_strategy=deployment_api_module.RollingUpdateReleaseStrategy()
    )
    client.jobs_service_update_deployment.assert_called()
    assert client.jobs_service_update_deployment._mock_mock_calls[0].kwargs["body"].spec.entrypoint == "new_entrypoint"


def test_deployment_stop(monkeypatch):
    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))

    deployment_spec = V1Deployment(
        name="ollama",
        spec=V1JobSpec(),
        endpoint=V1Endpoint(),
        strategy=None,
        autoscaling=V1AutoscalingSpec(),
        replicas=1,
    )

    client = MagicMock()

    called = False

    def fn(*_, **__):
        nonlocal called
        nonlocal deployment_spec
        if called:
            deployment_spec.replicas = 0
        else:
            called = True
        return V1ListDeploymentsResponse(deployments=[deployment_spec])

    client.jobs_service_list_deployments = fn
    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    def update(*_, body, **__):
        return body

    client.jobs_service_update_deployment = update

    deployment = deployment_module.Deployment(name="ollama")
    deployment._deployment_api._wait_on_stop = 0
    deployment.stop()
    assert deployment_spec.replicas == 0
