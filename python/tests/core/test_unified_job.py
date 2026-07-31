from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from lightning_sdk.job import Job
from lightning_sdk.lightning_cloud.openapi import V1Job, V1JobSpec, V1MultiMachineJob
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.mmt import MMT


def _teamspace() -> SimpleNamespace:
    return SimpleNamespace(
        id="teamspace-id",
        name="teamspace",
        owner=SimpleNamespace(name="owner"),
        default_cloud_account="default-cloud",
    )


def test_job_lookup_falls_back_to_multi_machine() -> None:
    teamspace = _teamspace()
    standalone_api = MagicMock()
    standalone_api.get_job_by_name.side_effect = ApiException(status=404)
    multi_api = MagicMock()
    multi_api.get_job_by_name.return_value = V1MultiMachineJob(
        id="mmt-id", name="distributed", machines=2, spec=V1JobSpec()
    )
    multi_api.get_num_machines.return_value = 2

    with patch("lightning_sdk.job._resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.job.JobApiV2", return_value=standalone_api
    ), patch("lightning_sdk.job.MMTApiV2", return_value=multi_api):
        job = Job("distributed", teamspace)

    assert job.is_multi_machine
    assert job.num_machines == 2
    standalone_api.get_job_by_name.assert_called_once()
    multi_api.get_job_by_name.assert_called_once()


def test_job_lookup_prefers_standalone_on_name_collision() -> None:
    teamspace = _teamspace()
    standalone_api = MagicMock()
    standalone_api.get_job_by_name.return_value = V1Job(id="job-id", name="train", spec=V1JobSpec())

    with patch("lightning_sdk.job._resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.job.JobApiV2", return_value=standalone_api
    ), patch("lightning_sdk.job.MMTApiV2") as multi_api:
        job = Job("train", teamspace)

    assert not job.is_multi_machine
    assert job.num_machines == 1
    assert job.machines == (job,)
    multi_api.assert_not_called()


def test_job_run_routes_multi_machine_submission() -> None:
    teamspace = _teamspace()
    multi_api = MagicMock()
    multi_api.submit_job.return_value = V1MultiMachineJob(
        id="mmt-id", name="distributed", machines=3, spec=V1JobSpec()
    )
    multi_api.get_num_machines.return_value = 3
    cloud_api = MagicMock()
    cloud_api.resolve_cloud_account.return_value = "cloud-id"

    with patch("lightning_sdk.job._resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.job._resolve_default_cloud_account", return_value=None
    ), patch("lightning_sdk.job.CloudAccountApi", return_value=cloud_api), patch(
        "lightning_sdk.job.MMTApiV2", return_value=multi_api
    ):
        job = Job.run(
            name="distributed",
            machine="CPU",
            cloud="aws",
            image="ubuntu",
            teamspace=teamspace,
            num_machines=3,
        )

    assert type(job) is Job
    assert job.is_multi_machine
    assert job.num_machines == 3
    assert multi_api.submit_job.call_args.kwargs["num_machines"] == 3


def test_mmt_run_returns_compatibility_subclass() -> None:
    teamspace = _teamspace()
    multi_api = MagicMock()
    multi_api.submit_job.return_value = V1MultiMachineJob(
        id="mmt-id", name="distributed", machines=2, spec=V1JobSpec()
    )
    cloud_api = MagicMock()
    cloud_api.resolve_cloud_account.return_value = "cloud-id"

    with patch("lightning_sdk.job._resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.job._resolve_default_cloud_account", return_value=None
    ), patch("lightning_sdk.job.CloudAccountApi", return_value=cloud_api), patch(
        "lightning_sdk.job.MMTApiV2", return_value=multi_api
    ):
        job = MMT.run(
            name="distributed",
            num_machines=2,
            machine="CPU",
            cloud="aws",
            image="ubuntu",
            teamspace=teamspace,
        )

    assert isinstance(job, MMT)
    assert isinstance(job, Job)
    assert job.is_multi_machine


def test_mmt_lookup_skips_standalone_api() -> None:
    teamspace = _teamspace()
    multi_api = MagicMock()
    multi_api.get_job_by_name.return_value = V1MultiMachineJob(
        id="mmt-id", name="distributed", machines=2, spec=V1JobSpec()
    )

    with patch("lightning_sdk.job._resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.job.JobApiV2"
    ) as standalone_api, patch("lightning_sdk.job.MMTApiV2", return_value=multi_api):
        job = MMT("distributed", teamspace)

    assert isinstance(job, MMT)
    assert job.is_multi_machine
    standalone_api.return_value.get_job_by_name.assert_not_called()
    multi_api.get_job_by_name.assert_called_once()
