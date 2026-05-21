import re
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lightning_sdk import CloudProvider, teamspace, user
from lightning_sdk import organization as organization_module
from lightning_sdk.api import deployment_api as deployment_api_module
from lightning_sdk.api.deployment_api import apply_change, to_env, to_health_check
from lightning_sdk.deployment import deployment as deployment_module
from lightning_sdk.deployment.deployment import AutoScaleConfig, Env, HttpHealthCheck, Secret
from lightning_sdk.lightning_cloud.openapi import (
    V1AutoscalingSpec,
    V1AutoscalingTargetMetric,
    V1BYOMSpec,
    V1Deployment,
    V1DeploymentStatus,
    V1Endpoint,
    V1EndpointAuth,
    V1EnvVar,
    V1JobSpec,
)
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.machine import Machine


def test_deployment_resolve_teamspace(monkeypatch):
    mock_org = MagicMock()
    mock_org.name = "org"
    monkeypatch.setattr(deployment_module, "_resolve_org", mock_org)
    monkeypatch.setattr(deployment_module, "Auth", MagicMock())
    monkeypatch.setattr(user, "UserApi", MagicMock())
    monkeypatch.setattr(teamspace, "TeamspaceApi", MagicMock())
    monkeypatch.setattr(deployment_module, "_get_cluster", MagicMock())
    monkeypatch.setattr(deployment_module, "DeploymentApi", MagicMock())
    resolve_teamspace_mock = MagicMock()
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", resolve_teamspace_mock)

    deployment = deployment_module.Deployment(name="name", teamspace="teamspace", org="org", user="user")
    kwargs = resolve_teamspace_mock._mock_mock_calls[0].kwargs
    assert kwargs["teamspace"] == "teamspace"
    assert kwargs["org"] == "org"
    assert kwargs["user"] == "user"
    assert isinstance(deployment._user, user.User)


def test_deployment_export_request_captures_wrapper(tmp_path):
    result = object()
    export_mock = MagicMock(return_value=result)

    deployment = object.__new__(deployment_module.Deployment)
    deployment._deployment = SimpleNamespace(id="deployment-id")
    deployment._deployment_api = SimpleNamespace(export_request_captures=export_mock)
    deployment._teamspace = SimpleNamespace(id="project-id")

    assert (
        deployment.export_request_captures(
            start="2026-04-20T00:00:00Z",
            end="2026-04-22T00:00:00Z",
            output_dir=tmp_path,
            paths=["/v1/chat/completions"],
            status_codes=[200],
            strict=True,
            request_timeout=5,
            overwrite=True,
            remote_path="lightning_storage/blackbox-exports/daily",
        )
        is result
    )
    export_mock.assert_called_once_with(
        deployment._deployment,
        start="2026-04-20T00:00:00Z",
        end="2026-04-22T00:00:00Z",
        output_dir=tmp_path,
        paths=["/v1/chat/completions"],
        include_all_paths=False,
        status_codes=[200],
        strict=True,
        request_timeout=5,
        overwrite=True,
        remote_path="lightning_storage/blackbox-exports/daily",
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

    with pytest.raises(
        ValueError, match=r"Either metric and threshold, or target_metrics \(for multiple\) can be provided\."
    ):
        deployment_api_module.to_autoscaling(
            AutoScaleConfig(
                max_replicas=2,
                min_replicas=2,
                metric="CPU",
                threshold=80,
                target_metrics=[deployment_api_module.AutoScalingMetric(name="GPU", target=70)],
            ),
            replicas=1,
        )

    with pytest.raises(
        ValueError, match=r"Either metric and threshold, or target_metrics \(for multiple\) can be provided\."
    ):
        deployment_api_module.to_autoscaling(
            AutoScaleConfig(
                max_replicas=2,
                min_replicas=2,
                metric="CPU",
                target_metrics=[deployment_api_module.AutoScalingMetric(name="GPU", target=70)],
            ),
            replicas=1,
        )

    with pytest.raises(
        ValueError, match=r"Either metric and threshold, or target_metrics \(for multiple\) can be provided\."
    ):
        deployment_api_module.to_autoscaling(
            AutoScaleConfig(
                max_replicas=2,
                min_replicas=2,
                threshold=80,
                target_metrics=[deployment_api_module.AutoScalingMetric(name="GPU", target=70)],
            ),
            replicas=1,
        )

    with pytest.raises(ValueError, match="The target_metrics must be provided."):
        deployment_api_module.to_autoscaling(
            AutoScaleConfig(max_replicas=2, min_replicas=2, target_metrics=[]),
            replicas=1,
        )

    with pytest.raises(
        ValueError,
        match=re.escape(
            f"The autoscaling metric is required. Currently supported metrics are {deployment_api_module._METRICS}"
        ),
    ):
        deployment_api_module.to_autoscaling(
            AutoScaleConfig(
                max_replicas=2,
                min_replicas=2,
                target_metrics=[deployment_api_module.AutoScalingMetric(name=None, target=70)],
            ),
            replicas=1,
        )

    with pytest.raises(
        ValueError,
        match=re.escape(
            f"The autoscaling metric is required. Currently supported metrics are {deployment_api_module._METRICS}"
        ),
    ):
        deployment_api_module.to_autoscaling(
            AutoScaleConfig(
                max_replicas=2,
                min_replicas=2,
                target_metrics=[deployment_api_module.AutoScalingMetric(name="DoesNotExist", target=70)],
            ),
            replicas=1,
        )

    with pytest.raises(ValueError, match="The autoscaling threshold should be defined between 0 and 100."):
        deployment_api_module.to_autoscaling(
            AutoScaleConfig(
                max_replicas=2,
                min_replicas=2,
                target_metrics=[deployment_api_module.AutoScalingMetric(name="GPU", target=-1)],
            ),
            replicas=1,
        )

    with pytest.raises(ValueError, match="The autoscaling threshold should be defined between 0 and 100."):
        deployment_api_module.to_autoscaling(
            AutoScaleConfig(
                max_replicas=2,
                min_replicas=2,
                target_metrics=[deployment_api_module.AutoScalingMetric(name="GPU", target=101)],
            ),
            replicas=1,
        )

    autoscaling = deployment_api_module.to_autoscaling(
        AutoScaleConfig(max_replicas=2, min_replicas=2, metric="CPU", threshold=100),
        replicas=1,
    )
    assert autoscaling.min_replicas == 2
    assert autoscaling.max_replicas == 2
    assert len(autoscaling.target_metric) == 1
    metric = autoscaling.target_metric[0]
    assert metric.name == "CPU"
    assert metric.target == "100"

    autoscaling_with_multiple_metrics = deployment_api_module.to_autoscaling(
        AutoScaleConfig(
            max_replicas=2,
            min_replicas=2,
            target_metrics=[
                deployment_api_module.AutoScalingMetric(name="CPU", target=80),
                deployment_api_module.AutoScalingMetric(name="GPU", target=75),
            ],
        ),
        replicas=1,
    )

    assert isinstance(autoscaling_with_multiple_metrics.target_metric[0], V1AutoscalingTargetMetric)

    assert autoscaling_with_multiple_metrics.min_replicas == 2
    assert autoscaling_with_multiple_metrics.max_replicas == 2
    assert len(autoscaling_with_multiple_metrics.target_metric) == 2
    first_metric = autoscaling_with_multiple_metrics.target_metric[0]
    assert first_metric.name == "CPU"
    assert first_metric.target == "80"
    second_metric = autoscaling_with_multiple_metrics.target_metric[1]
    assert second_metric.name == "GPU"
    assert second_metric.target == "75"


def test_to_env():
    env = deployment_api_module.to_env({"key": "value"})
    assert env == [V1EnvVar(name="key", value="value")]

    env = deployment_api_module.to_env([Env("key", "value"), Secret("secret")])
    assert env == [V1EnvVar(name="key", value="value"), V1EnvVar(from_secret="secret")]


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
    monkeypatch.setattr(deployment_module, "Auth", MagicMock())
    monkeypatch.setattr(deployment_module, "UserApi", MagicMock())
    monkeypatch.setattr(deployment_module, "User", MagicMock())

    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))
    resolve_user_mock = MagicMock()
    monkeypatch.setattr(deployment_module, "_resolve_user", resolve_user_mock)

    monkeypatch.setattr(organization_module, "OrgApi", MagicMock())

    organization = organization_module.Organization(name="toto")
    monkeypatch.setattr(deployment_module, "_resolve_org", MagicMock(return_value=organization))

    client = MagicMock()

    def fn(*_, **__):
        raise ApiException(status=400, reason="Reason: Not Found")

    client.jobs_service_get_deployment_by_name = fn
    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    deployment = deployment_module.Deployment(name="ollama")
    with pytest.raises(ValueError, match="At least one port is required to reach your deployment."):
        deployment.start()

    deployment = deployment_module.Deployment()

    assert deployment._name.startswith("dep_")

    deployment = deployment_module.Deployment(name="ollama")

    resolve_user_mock.assert_called()

    assert deployment.name == "ollama"

    assert isinstance(deployment.org, organization_module.Organization)

    deployment.start(
        autoscale=AutoScaleConfig(
            metric="GPU",
            threshold=75,
        ),
        ports=[50],
        cloud_account="cluster_id",
        machine=Machine.L4,
        image="ollama/ollama:latest",
        quantity=2,
        include_credentials=False,
        commands=["cd /", "ls"],
    )
    client.jobs_service_create_deployment.assert_called()

    spec = client.jobs_service_create_deployment._mock_call_args_list[0].kwargs["body"].spec
    assert spec.include_credentials is False
    assert spec.quantity == 2
    assert spec.image == "ollama/ollama:latest"
    assert spec.cluster_id == "cluster_id"
    assert spec.command == "cd / && ls"

    with pytest.raises(RuntimeError, match="This deployment has already been started."):
        deployment.start()

    _deployment_api_mock = MagicMock()
    deployment._deployment_api = _deployment_api_mock
    status = V1DeploymentStatus(
        deleting_replicas=1,
        failing_replicas=2,
        pending_replicas=3,
        ready_replicas=4,
    )
    _deployment_mock = MagicMock()
    _deployment_mock.status = status
    _deployment_api_mock.get_deployment_by_name = MagicMock(return_value=_deployment_mock)
    assert deployment.deleting_replicas == 1
    assert deployment.failing_replicas == 2
    assert deployment.pending_replicas == 3
    assert deployment.running_replicas == 4


def test_deployment_start_with_cloud_provider(monkeypatch):
    monkeypatch.setattr(deployment_module, "Auth", MagicMock())
    monkeypatch.setattr(deployment_module, "UserApi", MagicMock())
    monkeypatch.setattr(deployment_module, "User", MagicMock())
    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))
    resolve_user_mock = MagicMock()
    monkeypatch.setattr(deployment_module, "_resolve_user", resolve_user_mock)
    # Create mock objects for the cluster-related API methods
    mock_cloud_account_api = MagicMock()
    mock_cloud_account_api.resolve_cloud_account.return_value = "gcp-public"

    # Patch the CloudAccountApi to return your mock
    monkeypatch.setattr(deployment_module, "CloudAccountApi", MagicMock(return_value=mock_cloud_account_api))

    monkeypatch.setattr(organization_module, "OrgApi", MagicMock())

    organization = organization_module.Organization(name="toto")
    monkeypatch.setattr(deployment_module, "_resolve_org", MagicMock(return_value=organization))

    client = MagicMock()

    def fn(*_, **__):
        raise ApiException(status=400, reason="Reason: Not Found")

    client.jobs_service_get_deployment_by_name = fn
    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    deployment = deployment_module.Deployment(name="ollama")

    deployment = deployment_module.Deployment()

    assert deployment._name.startswith("dep_")

    deployment = deployment_module.Deployment(name="ollama")

    resolve_user_mock.assert_called()

    assert deployment.name == "ollama"

    assert isinstance(deployment.org, organization_module.Organization)

    deployment.start(
        autoscale=AutoScaleConfig(
            metric="GPU",
            threshold=75,
        ),
        ports=[50],
        cloud_provider=CloudProvider.GCP,
        machine=Machine.L4,
        image="ollama/ollama:latest",
        quantity=2,
        include_credentials=False,
        commands=["cd /", "ls"],
    )
    client.jobs_service_create_deployment.assert_called()

    spec = client.jobs_service_create_deployment._mock_call_args_list[0].kwargs["body"].spec
    assert spec.include_credentials is False
    assert spec.quantity == 2
    assert spec.image == "ollama/ollama:latest"
    assert spec.cluster_id == "gcp-public"
    assert spec.command == "cd / && ls"

    with pytest.raises(RuntimeError, match="This deployment has already been started."):
        deployment.start()

    _deployment_api_mock = MagicMock()
    deployment._deployment_api = _deployment_api_mock
    status = V1DeploymentStatus(
        deleting_replicas=1,
        failing_replicas=2,
        pending_replicas=3,
        ready_replicas=4,
    )
    _deployment_mock = MagicMock()
    _deployment_mock.status = status
    _deployment_api_mock.get_deployment_by_name = MagicMock(return_value=_deployment_mock)
    assert deployment.deleting_replicas == 1
    assert deployment.failing_replicas == 2
    assert deployment.pending_replicas == 3
    assert deployment.running_replicas == 4

    mock_cloud_account_api.resolve_cloud_account.assert_called_once_with(
        teamspace_mock.id,
        cloud_account=None,
        cloud_provider=CloudProvider.GCP,
        default_cloud_account=teamspace_mock.default_cloud_account,
    )


def test_deployment_start_with_both_cloud_account_and_provider(monkeypatch):
    """Test that passing both cloud_account and cloud_provider raises an error."""
    monkeypatch.setattr(deployment_module, "Auth", MagicMock())
    monkeypatch.setattr(deployment_module, "UserApi", MagicMock())
    monkeypatch.setattr(deployment_module, "User", MagicMock())

    # Create mock objects for the cluster-related API methods
    mock_cloud_account_api = MagicMock()
    # Configure the mock to raise an error when both are provided
    mock_cloud_account_api.resolve_cloud_account.side_effect = ValueError(
        "Cannot specify both cloud_account and cloud_provider"
    )

    # Patch the CloudAccountApi to return your mock
    monkeypatch.setattr(deployment_module, "CloudAccountApi", MagicMock(return_value=mock_cloud_account_api))

    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    teamspace_mock.default_cloud_account = None
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))
    monkeypatch.setattr(deployment_module, "_resolve_user", MagicMock())

    monkeypatch.setattr(organization_module, "OrgApi", MagicMock())

    organization = organization_module.Organization(name="toto")
    monkeypatch.setattr(deployment_module, "_resolve_org", MagicMock(return_value=organization))

    client = MagicMock()

    def fn(*_, **__):
        raise ApiException(status=400, reason="Reason: Not Found")

    client.jobs_service_get_deployment_by_name = fn
    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    deployment = deployment_module.Deployment(name="ollama")

    # This should raise ValueError
    with pytest.raises(ValueError, match="Cannot specify both cloud_account and cloud_provider"):
        deployment.start(
            autoscale=AutoScaleConfig(
                metric="GPU",
                threshold=75,
            ),
            ports=[50],
            cloud_account="aws-public",  # Both specified
            cloud_provider=CloudProvider.GCP,  # Both specified
            machine=Machine.L4,
            image="ollama/ollama:latest",
            quantity=2,
            include_credentials=False,
            commands=["cd /", "ls"],
        )

    # Verify resolve_cloud_account was called with both parameters
    mock_cloud_account_api.resolve_cloud_account.assert_called_once_with(
        teamspace_mock.id,
        cloud_account="aws-public",
        cloud_provider=CloudProvider.GCP,
        default_cloud_account=None,
    )


def test_deployment_start_already_exist(monkeypatch):
    monkeypatch.setattr(deployment_module, "Auth", MagicMock())
    monkeypatch.setattr(deployment_module, "UserApi", MagicMock())
    monkeypatch.setattr(deployment_module, "User", MagicMock())
    monkeypatch.setattr(user, "UserApi", MagicMock())

    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))

    client = MagicMock()
    client.jobs_service_get_deployment_by_name.return_value = V1Deployment(name="ollama")
    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    deployment = deployment_module.Deployment(name="ollama")
    with pytest.raises(RuntimeError, match="This deployment has already been started."):
        deployment.start()


def test_deployment_update(monkeypatch):
    monkeypatch.setattr(deployment_module, "Auth", MagicMock())
    monkeypatch.setattr(deployment_module, "UserApi", MagicMock())
    monkeypatch.setattr(deployment_module, "User", MagicMock())
    monkeypatch.setattr(user, "UserApi", MagicMock())

    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))

    client = MagicMock()
    client.jobs_service_get_deployment_by_name.return_value = V1Deployment(
        name="ollama",
        spec=V1JobSpec(quantity=2, include_credentials=False),
        endpoint=V1Endpoint(),
        strategy=None,
        release_id="release-id",
    )

    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    deployment = deployment_module.Deployment(name="ollama")

    with pytest.raises(RuntimeError, match="When doing a new release, a release strategy needs to be defined."):
        deployment.update(entrypoint="new_entrypoint")

    deployment.update(
        entrypoint="new_entrypoint",
        release_strategy=deployment_api_module.RollingUpdateReleaseStrategy(),
        health_check=HttpHealthCheck(path="/health", port=8000),
        include_credentials=True,
        command="python server.py",
    )
    client.jobs_service_update_deployment.assert_called()
    assert client.jobs_service_update_deployment._mock_mock_calls[0].kwargs["body"].spec.entrypoint == "new_entrypoint"
    readiness_probe = client.jobs_service_update_deployment._mock_mock_calls[0].kwargs["body"].spec.readiness_probe
    assert readiness_probe.http_get.path == "/health"
    assert readiness_probe.http_get.port == 8000
    assert deployment.release_id == "release-id"
    assert deployment.quantity == 2
    assert deployment.include_credentials is True
    assert deployment.entrypoint == "new_entrypoint"
    assert deployment.command == "python server.py"

    deployment.update(
        entrypoint="new_entrypoint",
        release_strategy=deployment_api_module.RollingUpdateReleaseStrategy(),
        health_check=HttpHealthCheck(path="/health", port=8000),
        include_credentials=False,
    )
    client.jobs_service_update_deployment.assert_called()
    assert client.jobs_service_update_deployment._mock_mock_calls[0].kwargs["body"].spec.entrypoint == "new_entrypoint"
    readiness_probe = client.jobs_service_update_deployment._mock_mock_calls[0].kwargs["body"].spec.readiness_probe
    assert readiness_probe.http_get.path == "/health"
    assert readiness_probe.http_get.port == 8000
    assert deployment.release_id == "release-id"
    assert deployment.quantity == 2
    assert deployment.include_credentials is False
    assert deployment.entrypoint == "new_entrypoint"
    assert deployment.command == "python server.py"

    deployment.update(include_credentials=None, command="python server2.py")
    assert deployment.include_credentials is False
    assert readiness_probe.http_get.path == "/health"
    assert readiness_probe.http_get.port == 8000
    assert deployment.entrypoint == "new_entrypoint"
    assert deployment.command == "python server2.py"


def test_deployment_update_name(monkeypatch):
    monkeypatch.setattr(deployment_module, "Auth", MagicMock())
    monkeypatch.setattr(deployment_module, "UserApi", MagicMock())
    monkeypatch.setattr(deployment_module, "User", MagicMock())
    monkeypatch.setattr(user, "UserApi", MagicMock())

    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))

    client = MagicMock()
    client.jobs_service_get_deployment_by_name.return_value = V1Deployment(name="ollama", spec=V1JobSpec())

    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    deployment = deployment_module.Deployment(name="ollama")

    with pytest.raises(RuntimeError, match="When doing a new release, a release strategy needs to be defined."):
        deployment.update(entrypoint="new_entrypoint")

    assert deployment.name == "ollama"
    deployment.update(name="new_entrypoint")
    assert deployment.name == "new_entrypoint"


def test_deployment_update_replicas(monkeypatch):
    monkeypatch.setattr(deployment_module, "Auth", MagicMock())
    monkeypatch.setattr(deployment_module, "UserApi", MagicMock())
    monkeypatch.setattr(deployment_module, "User", MagicMock())
    monkeypatch.setattr(user, "UserApi", MagicMock())

    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))

    client = MagicMock()
    client.jobs_service_get_deployment_by_name.return_value = V1Deployment(replicas=1, spec=V1JobSpec())

    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    deployment = deployment_module.Deployment(name="ollama")

    with pytest.raises(RuntimeError, match="When doing a new release, a release strategy needs to be defined."):
        deployment.update(entrypoint="new_entrypoint")

    assert deployment.replicas == 1
    deployment.update()
    assert deployment.replicas == 1
    deployment.update(replicas=0)
    assert deployment.replicas == 0


def test_deployment_update_strategy(monkeypatch):
    monkeypatch.setattr(deployment_module, "Auth", MagicMock())
    monkeypatch.setattr(deployment_module, "UserApi", MagicMock())
    monkeypatch.setattr(deployment_module, "User", MagicMock())
    monkeypatch.setattr(user, "UserApi", MagicMock())

    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))

    client = MagicMock()
    client.jobs_service_get_deployment_by_name.return_value = V1Deployment(spec=V1JobSpec())

    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    deployment = deployment_module.Deployment(name="ollama")

    with pytest.raises(RuntimeError, match="When doing a new release, a release strategy needs to be defined."):
        deployment.update(entrypoint="new_entrypoint")

    assert deployment._deployment.strategy is None
    deployment.update()
    assert deployment._deployment.strategy is not None
    deployment.update(release_strategy=deployment_api_module.RollingUpdateReleaseStrategy())
    assert deployment._deployment.strategy is not None


def test_deployment_stop(monkeypatch):
    monkeypatch.setattr(deployment_module, "Auth", MagicMock())
    monkeypatch.setattr(deployment_module, "UserApi", MagicMock())
    monkeypatch.setattr(deployment_module, "User", MagicMock())
    monkeypatch.setattr(user, "UserApi", MagicMock())

    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))

    deployment_spec = V1Deployment(
        name="ollama",
        spec=V1JobSpec(image="my-image"),
        endpoint=V1Endpoint(),
        strategy=None,
        autoscaling=V1AutoscalingSpec(max_replicas=1, min_replicas=0),
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
        return deployment_spec

    client.jobs_service_get_deployment_by_name = fn
    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    def update(*_, body, **__):
        return body

    client.jobs_service_update_deployment = update

    deployment = deployment_module.Deployment(name="ollama")
    deployment._deployment_api._wait_on_stop = 0
    assert not deployment.is_stopped
    assert deployment.min_replicas == 0
    assert deployment.max_replicas == 1
    deployment.stop()
    assert deployment.min_replicas == 0
    assert deployment.max_replicas == 0
    assert deployment_spec.replicas == 0
    assert deployment.is_stopped
    assert deployment.image == "my-image"


def test_deployment_get(monkeypatch):
    monkeypatch.setattr(deployment_module, "Auth", MagicMock())
    monkeypatch.setattr(deployment_module, "UserApi", MagicMock())
    monkeypatch.setattr(deployment_module, "User", MagicMock())
    monkeypatch.setattr(user, "UserApi", MagicMock())
    requests_mock = MagicMock()
    monkeypatch.setattr(deployment_module, "requests", requests_mock)

    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))

    client = MagicMock()
    client.jobs_service_get_deployment_by_name.return_value = V1Deployment(
        name="ollama",
        spec=V1JobSpec(),
        endpoint=V1Endpoint(
            auth=V1EndpointAuth(
                user_api_key=True,
            )
        ),
        status=V1DeploymentStatus(
            urls=["http://11434-dep-01jb23cf67pj9yt20jfcxds8nj-d.cloudspaces.local.litng.ai:8118"]
        ),
        strategy=None,
    )

    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    deployment = deployment_module.Deployment(name="ollama")

    deployment.get("/")

    requests_mock.Session().get.assert_called()


def test_deployment_post(monkeypatch):
    monkeypatch.setattr(deployment_module, "Auth", MagicMock())
    monkeypatch.setattr(deployment_module, "UserApi", MagicMock())
    monkeypatch.setattr(deployment_module, "User", MagicMock())
    monkeypatch.setattr(user, "UserApi", MagicMock())
    requests_mock = MagicMock()
    monkeypatch.setattr(deployment_module, "requests", requests_mock)

    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))

    client = MagicMock()
    url = "http://11434-dep-01jb23cf67pj9yt20jfcxds8nj-d.cloudspaces.local.litng.ai:8118"
    client.jobs_service_get_deployment_by_name.return_value = V1Deployment(
        name="ollama",
        spec=V1JobSpec(),
        endpoint=V1Endpoint(
            auth=V1EndpointAuth(
                user_api_key=True,
            )
        ),
        status=V1DeploymentStatus(urls=[url]),
        strategy=None,
    )

    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    deployment = deployment_module.Deployment(name="ollama")

    json = {"model": "llama3.1", "messages": [{"role": "user", "content": "why is the sky blue?"}], "stream": True}
    deployment.post("/api/chat", json=json)

    requests_mock.Session().post.assert_called_with(f"{url}/api/chat", json=json, verify=False)


def test_deployment_put(monkeypatch):
    monkeypatch.setattr(deployment_module, "Auth", MagicMock())
    monkeypatch.setattr(deployment_module, "UserApi", MagicMock())
    monkeypatch.setattr(deployment_module, "User", MagicMock())
    monkeypatch.setattr(user, "UserApi", MagicMock())
    requests_mock = MagicMock()
    monkeypatch.setattr(deployment_module, "requests", requests_mock)

    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))

    client = MagicMock()
    url = "http://11434-dep-01jb23cf67pj9yt20jfcxds8nj-d.cloudspaces.local.litng.ai:8118"
    client.jobs_service_get_deployment_by_name.return_value = V1Deployment(
        name="ollama",
        spec=V1JobSpec(),
        endpoint=V1Endpoint(
            auth=V1EndpointAuth(
                user_api_key=True,
            )
        ),
        status=V1DeploymentStatus(urls=[url]),
        strategy=None,
    )

    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    deployment = deployment_module.Deployment(name="ollama")

    deployment.put("")

    requests_mock.Session().put.assert_called_with(f"{url}/", verify=False)


def test_deployment_delete(monkeypatch):
    monkeypatch.setattr(deployment_module, "Auth", MagicMock())
    monkeypatch.setattr(deployment_module, "UserApi", MagicMock())
    monkeypatch.setattr(deployment_module, "User", MagicMock())
    monkeypatch.setattr(user, "UserApi", MagicMock())
    requests_mock = MagicMock()
    monkeypatch.setattr(deployment_module, "requests", requests_mock)

    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))

    client = MagicMock()
    url = "http://11434-dep-01jb23cf67pj9yt20jfcxds8nj-d.cloudspaces.local.litng.ai:8118"
    client.jobs_service_get_deployment_by_name.return_value = V1Deployment(
        name="ollama",
        spec=V1JobSpec(),
        endpoint=V1Endpoint(
            auth=V1EndpointAuth(
                user_api_key=True,
            )
        ),
        status=V1DeploymentStatus(urls=[url]),
        strategy=None,
    )

    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    deployment = deployment_module.Deployment(name="ollama")

    deployment.delete("/")

    requests_mock.Session().delete.assert_called_with(f"{url}/", verify=False)


def test_to_spec():
    with pytest.raises(ValueError, match="The cloud account should be defined."):
        deployment_api_module.to_spec(None, None, None, None, None)

    with pytest.raises(ValueError, match="The machine should be defined."):
        deployment_api_module.to_spec("cluster-id", None, None, None, None)

    with pytest.raises(ValueError, match="The image should be defined."):
        deployment_api_module.to_spec("cluster-id", Machine.CPU, None, None, None)

    with pytest.raises(ValueError, match="The command should be defined."):
        deployment_api_module.to_spec("cluster-id", Machine.CPU, None, None, None, cloudspace_id="cloudspace_id")

    deployment_api_module.to_spec("cluster-id", Machine.CPU, None, None, "command", cloudspace_id="cloudspace_id")

    deployment_api_module.to_spec("cluster-id", Machine.CPU, "image", None, None)


def test_compose_commands():
    commands = ["python server.py &", "python server.py &"]
    command = deployment_api_module.compose_commands(commands)
    assert command == "( python server.py & ) && ( python server.py & )"

    commands = ["python server.py &", "ls", "python server.py &"]
    command = deployment_api_module.compose_commands(commands)
    assert command == "( python server.py & ) && ls && ( python server.py & )"


def test_to_health_check_empty():
    health_check = deployment_api_module.to_health_check()
    assert health_check.failure_threshold == 3600
    assert health_check.initial_delay_seconds == 0
    assert health_check.interval_seconds == 1
    assert health_check.timeout_seconds == 60

    health_check = deployment_api_module.to_health_check(None, False)
    assert health_check is None


def test_apply_change():
    to_health_check()

    spec = V1JobSpec()
    assert apply_change(spec, "env", to_env({"NAME": "VALUE"}))

    spec = V1JobSpec()
    assert not apply_change(spec, "env", to_env(None))

    spec = V1JobSpec()
    assert apply_change(spec, "readiness_probe", to_health_check(None))


def test_deployment_start_with_path_mappings(monkeypatch):
    monkeypatch.setattr(deployment_module, "Auth", MagicMock())
    monkeypatch.setattr(deployment_module, "UserApi", MagicMock())
    monkeypatch.setattr(deployment_module, "User", MagicMock())

    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))
    monkeypatch.setattr(deployment_module, "_resolve_user", MagicMock())

    monkeypatch.setattr(organization_module, "OrgApi", MagicMock())

    organization = organization_module.Organization(name="toto")
    monkeypatch.setattr(deployment_module, "_resolve_org", MagicMock(return_value=organization))

    client = MagicMock()

    def fn(*_, **__):
        raise ApiException(status=400, reason="Reason: Not Found")

    client.jobs_service_get_deployment_by_name = fn
    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    deployment = deployment_module.Deployment(name="test-deployment")

    path_mappings = {"/app/data": "my-connection:path/to/data", "/app/models": "models-connection:models"}

    deployment.start(
        ports=[8080],
        cloud_account="cluster_id",
        machine=Machine.L4,
        image="test:latest",
        path_mappings=path_mappings,
    )

    client.jobs_service_create_deployment.assert_called()
    spec = client.jobs_service_create_deployment._mock_call_args_list[0].kwargs["body"].spec
    assert spec.path_mappings is not None
    assert len(spec.path_mappings) == 2


def test_deployment_update_with_path_mappings(monkeypatch):
    monkeypatch.setattr(deployment_module, "Auth", MagicMock())
    monkeypatch.setattr(deployment_module, "UserApi", MagicMock())
    monkeypatch.setattr(deployment_module, "User", MagicMock())
    monkeypatch.setattr(user, "UserApi", MagicMock())

    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))

    client = MagicMock()
    client.jobs_service_get_deployment_by_name.return_value = V1Deployment(
        name="test-deployment",
        spec=V1JobSpec(quantity=1, include_credentials=False),
        endpoint=V1Endpoint(),
        strategy=None,
        release_id="release-id",
    )

    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    deployment = deployment_module.Deployment(name="test-deployment")

    path_mappings = {"/app/data": "my-connection:path/to/data", "/app/models": "models-connection:models"}

    deployment.update(
        entrypoint="new_entrypoint",
        release_strategy=deployment_api_module.RollingUpdateReleaseStrategy(),
        path_mappings=path_mappings,
    )

    client.jobs_service_update_deployment.assert_called()
    spec = client.jobs_service_update_deployment._mock_mock_calls[0].kwargs["body"].spec
    assert spec.path_mappings is not None
    assert len(spec.path_mappings) == 2


def test_deployment_start_byom_builds_spec(monkeypatch):
    monkeypatch.setattr(deployment_module, "Auth", MagicMock())
    monkeypatch.setattr(deployment_module, "UserApi", MagicMock())
    monkeypatch.setattr(deployment_module, "User", MagicMock())

    teamspace_mock = MagicMock()
    teamspace_mock.id = "project_id"
    monkeypatch.setattr(deployment_module, "_resolve_teamspace", MagicMock(return_value=teamspace_mock))
    monkeypatch.setattr(deployment_module, "_resolve_user", MagicMock())
    monkeypatch.setattr(organization_module, "OrgApi", MagicMock())
    monkeypatch.setattr(
        deployment_module, "_resolve_org", MagicMock(return_value=organization_module.Organization(name="toto"))
    )

    client = MagicMock()
    client.jobs_service_get_deployment_by_name.side_effect = ApiException(status=400, reason="Reason: Not Found")
    monkeypatch.setattr(deployment_api_module, "LightningClient", MagicMock(return_value=client))

    deployment = deployment_module.Deployment(name="llama")
    deployment.start(
        ports=[8000],
        cloud_account="cluster_id",
        machine=Machine.L4,
        model="meta-llama/Llama-3-8B",
        tensor_parallel_size=4,
        max_model_len=8192,
        quantization="fp8",
        extra_vllm_args=["--enable-chunked-prefill"],
        acknowledged_warnings=["BYOM_INSUFFICIENT_VRAM_ESTIMATE"],
    )

    body = client.jobs_service_create_deployment._mock_call_args_list[0].kwargs["body"]
    assert isinstance(body.byom_spec, V1BYOMSpec)
    assert body.byom_spec.served_model_name == "meta-llama/Llama-3-8B"
    assert body.byom_spec.weight_source == "WEIGHT_SOURCE_HUGGINGFACE"
    assert body.byom_spec.tensor_parallel_size == 4
    assert body.byom_spec.max_model_len == 8192
    assert body.byom_spec.quantization == "fp8"
    assert body.byom_spec.extra_vllm_args == ["--enable-chunked-prefill"]
    assert body.acknowledged_warnings == ["BYOM_INSUFFICIENT_VRAM_ESTIMATE"]
