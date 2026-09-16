from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from lightning_sdk import Machine, Status, Studio
from lightning_sdk.api.cloud_account_api import CloudAccountApi
from lightning_sdk.api.utils import _machine_to_compute_name
from lightning_sdk.job import Job
from lightning_sdk.lightning_cloud.openapi import V1Job, V1JobSpec, V1MultiMachineJob


@pytest.fixture()
def cloud_api(monkeypatch):
    monkeypatch.setattr("lightning_sdk.utils.logging.cached_lightning_client", MagicMock())
    api = CloudAccountApi()
    api.get_cloud_account_non_org = MagicMock(
        side_effect=lambda teamspace, cloud: SimpleNamespace(
            spec=SimpleNamespace(driver="MACHINE" if cloud == "custom-metal" else "AWS", machine_v1=None)
        )
    )
    api.resolve_cloud_account = MagicMock(side_effect=lambda *args, **kwargs: kwargs["cloud"])
    return api


@pytest.mark.parametrize("count", [1, 2, 4, 8])
@pytest.mark.parametrize("cloud", ["custom-metal", "aws-account"])
@pytest.mark.parametrize("as_string", [False, True])
def test_provider_resolution_preserves_public_h200_name(cloud_api, count, cloud, as_string):
    name = "H200" if count == 1 else f"H200_X_{count}"
    machine = getattr(Machine, name)
    resolved = cloud_api.resolve_machine(name if as_string else machine, "teamspace", cloud)
    prefix = "lit-h200-141gb" if cloud == "custom-metal" else "lit-h200x"
    assert _machine_to_compute_name(resolved) == f"{prefix}-{count}"
    assert str(resolved) == name
    assert machine.instance_type is None
    assert machine.slug == f"lit-h200x-{count}"


def test_non_h200_does_not_fetch_provider(cloud_api):
    for machine in (Machine.H100, Machine.CPU, "custom-instance"):
        assert cloud_api.resolve_machine(machine, "teamspace", "custom-metal") is machine
    cloud_api.get_cloud_account_non_org.assert_not_called()


@pytest.mark.parametrize("num_machines", [1, 2])
@pytest.mark.parametrize("cloud", ["custom-metal", "aws-account"])
def test_job_submission_resolves_h200_for_destination(cloud_api, num_machines, cloud):
    teamspace = MagicMock()
    teamspace.id = "project"
    teamspace.default_cloud_account = None
    api = MagicMock()
    result = (
        V1Job(id="job", spec=V1JobSpec())
        if num_machines == 1
        else V1MultiMachineJob(id="mmt", machines=2, spec=V1JobSpec())
    )
    api.submit_job.return_value = result
    api.get_num_machines.return_value = num_machines
    with patch("lightning_sdk.job._resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.job.CloudAccountApi", return_value=cloud_api
    ), patch("lightning_sdk.job.JobApiV2", return_value=api), patch("lightning_sdk.job.MMTApiV2", return_value=api):
        Job.run(
            "train",
            machine=Machine.H200_X_2,
            image="ubuntu",
            cloud=cloud,
            teamspace=teamspace,
            num_machines=num_machines,
        )
    requested = api.submit_job.call_args.kwargs["machine"]
    assert _machine_to_compute_name(requested) == ("lit-h200-141gb-2" if cloud == "custom-metal" else "lit-h200x-2")


@pytest.mark.parametrize("cloud", ["custom-metal", "aws-account"])
def test_studio_start_and_switch_resolve_h200(cloud_api, cloud):
    studio = Studio.__new__(Studio)
    studio._teamspace = MagicMock(id="project")
    studio._studio = SimpleNamespace(id="studio", cluster_id=cloud)
    studio._studio_api = MagicMock()
    studio._cloud_account_api = cloud_api
    studio._setup = MagicMock()
    studio.show_progress = False
    with patch.object(Studio, "status", new_callable=PropertyMock, return_value=Status.Stopped):
        studio.start(Machine.H200_X_2, interruptible=False)
    machine = studio._studio_api.start_studio.call_args.args[2]
    assert _machine_to_compute_name(machine) == ("lit-h200-141gb-2" if cloud == "custom-metal" else "lit-h200x-2")
    with patch.object(Studio, "status", new_callable=PropertyMock, return_value=Status.Running):
        studio.switch_machine(Machine.H200_X_4)
    machine = studio._studio_api.switch_studio_machine.call_args.args[2]
    assert _machine_to_compute_name(machine) == ("lit-h200-141gb-4" if cloud == "custom-metal" else "lit-h200x-4")


@pytest.mark.parametrize("cloud", ["custom-metal", "aws-account"])
def test_deployment_create_and_update_resolve_h200(cloud_api, cloud):
    from lightning_sdk.deployment import Deployment

    deployment = Deployment.__new__(Deployment)
    deployment._name = "serve"
    deployment._is_created = False
    deployment._cloud_account = None
    deployment._cloud_account_api = cloud_api
    deployment._teamspace = MagicMock(id="project")
    deployment._deployment_api = MagicMock()
    deployment._deployment_api.create_deployment.side_effect = lambda body, **kwargs: body
    deployment._deployment_api.update_deployment.side_effect = lambda body, **kwargs: body
    with patch("lightning_sdk.deployment.raise_access_error_if_not_allowed"):
        deployment.start(image="nginx", cloud=cloud, machine=Machine.H200_X_2, ports=[80])
        body = deployment._deployment_api.create_deployment.call_args.args[0]
        assert body.spec.instance_name == ("lit-h200-141gb-2" if cloud == "custom-metal" else "lit-h200x-2")
        deployment.update(machine=Machine.H200_X_4)
        requested = deployment._deployment_api.update_deployment.call_args.kwargs["machine"]
        assert _machine_to_compute_name(requested) == ("lit-h200-141gb-4" if cloud == "custom-metal" else "lit-h200x-4")
        other_cloud = "aws-account" if cloud == "custom-metal" else "custom-metal"
        deployment.update(cloud=other_cloud)
        requested = deployment._deployment_api.update_deployment.call_args.kwargs["machine"]
        assert _machine_to_compute_name(requested) == (
            "lit-h200-141gb-2" if other_cloud == "custom-metal" else "lit-h200x-2"
        )


@pytest.mark.parametrize("driver, expected", [(None, "lit-h200-141gb-1"), ("AWS", "lit-h200x-1")])
def test_machine_config_respects_driver_override(cloud_api, driver, expected):
    cloud_api.get_cloud_account_non_org.return_value = SimpleNamespace(
        spec=SimpleNamespace(driver=driver, machine_v1=object())
    )
    cloud_api.get_cloud_account_non_org.side_effect = None
    assert _machine_to_compute_name(cloud_api.resolve_machine(Machine.H200, "project", "custom-metal")) == expected
