import os
from contextlib import nullcontext
from pathlib import Path
from unittest import mock

import pytest

from lightning_sdk.job import Job
from lightning_sdk.lightning_cloud.openapi import (
    Externalv1LightningappInstance,
    V1ClusterAccelerator,
    V1Job,
    V1ModelVersionArchive,
    V1MultiMachineJob,
)
from lightning_sdk.mmt import MMT
from lightning_sdk.organization import Organization
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User


@pytest.mark.parametrize("user", ["user-abc", None, -1])
@pytest.mark.parametrize("org", ["org-abc", None, -1])
@mock.patch.dict(os.environ, clear=True)
def test_teamspace_init(
    internal_teamspace_api_list_mocker, internal_user_api_mocker, internal_get_org_api_mocker, user, org
):
    # convert -1 to actual objects since we can't do that outside without mocking API calls
    if user == -1:
        user = User("user-abc")

    if org == -1:
        org = Organization("org-abc")

    if user is None and org is None:
        context = pytest.raises(
            RuntimeError,
            match="Neither user or org are specified, but one of them has to be the owner of the Teamspace",
        )
    elif user is not None and org is not None:
        context = pytest.raises(
            ValueError, match="User and org are mutually exclusive. Please only specify the one who owns the teamspace."
        )
    else:
        context = nullcontext()

    with context:
        Teamspace("ts-abc", user=user, org=org)


@pytest.mark.parametrize("user", ["user-abc", None, -1])
@pytest.mark.parametrize("org", ["org-abc", None, -1])
def test_teamspace_init_env(
    internal_teamspace_api_list_mocker, internal_user_api_mocker, internal_get_org_api_mocker, user, org
):
    if user is None and org is None:
        context = pytest.raises(
            RuntimeError,
            match="Neither user or org are specified, but one of them has to be the owner of the Teamspace",
        )
    elif user is not None and org is not None:
        if user == -1 or org == -1:
            context = nullcontext()
        else:
            context = pytest.raises(
                ValueError,
                match="User and org are mutually exclusive. Please only specify the one who owns the teamspace.",
            )
    else:
        context = nullcontext()

    new_dict = {}
    if user == -1:
        new_dict["LIGHTNING_USERNAME"] = "user-abc"
        user = None

    if org == -1:
        new_dict["LIGHTNING_ORG"] = "org-abc"
        org = None

    with context, mock.patch.dict(os.environ, new_dict, clear=True):
        print(user, org)
        Teamspace("ts-abc", user=user, org=org)


@mock.patch.dict(os.environ, clear=True)
def test_teamspace_list_clusters_studios_user(
    internal_studio_api_list_mocker,
    internal_user_api_mocker,
    internal_teamspace_api_cluster_list_mocker,
    internal_teamspace_api_list_mocker,
    internal_auth_mocker,
):
    ts = Teamspace("ts-abc", user="user-abc")

    studios = ts.studios

    # 2 clusters * 3 studios per cluster
    assert len(studios) == 6


@mock.patch.dict(os.environ, clear=True)
def test_teamspace_list_clusters_studios_org(
    internal_studio_api_list_mocker,
    internal_get_org_api_mocker,
    internal_teamspace_api_cluster_list_mocker,
    internal_teamspace_api_list_mocker,
    internal_auth_mocker,
):
    ts = Teamspace("ts-abc", org="org-abc")

    studios = ts.studios

    # 2 clusters * 3 studios per cluster
    assert len(studios) == 6


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"user": "user-abc"}, "Teamspace(name=ts-abc, owner=User(name=user-abc))"),
        ({"org": "org-abc"}, "Teamspace(name=ts-abc, owner=Organization(name=org-abc))"),
    ],
)
def test_repr(
    internal_teamspace_api_list_mocker,
    internal_get_org_api_mocker,
    internal_user_api_mocker,
    internal_auth_mocker,
    kwargs,
    expected,
):
    ts = Teamspace(name="ts-abc", **kwargs)
    assert repr(ts) == expected


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"user": "user-abc"}, "Teamspace(name=ts-abc, owner=User(name=user-abc))"),
        ({"org": "org-abc"}, "Teamspace(name=ts-abc, owner=Organization(name=org-abc))"),
    ],
)
def test_str(
    internal_teamspace_api_list_mocker,
    internal_get_org_api_mocker,
    internal_user_api_mocker,
    internal_auth_mocker,
    kwargs,
    expected,
):
    ts = Teamspace(name="ts-abc", **kwargs)
    assert str(ts) == expected


def test_teamspace_error_user_and_org():
    with pytest.raises(
        ValueError, match="User and org are mutually exclusive. Please only specify the one who owns the teamspace."
    ):
        Teamspace(name="ts-abc", user="foo", org="bar")


def test_create_agent(
    internal_teamspace_api_list_mocker,
    internal_user_api_mocker,
    internal_auth_mocker,
    internal_teamspace_api_create_agent_mocker,
    internal_agents_api_get_agent_mocker,
):
    ts = Teamspace("ts-abc", user="user-abc")
    agent = ts.create_agent(
        name="test-sdk",
        base_url="test-sdk",
        api_key="test-sdk",
        model="test-sdk",
    )
    assert agent._agent.name == "test-sdk"


@mock.patch.dict(os.environ, {"LIGHTNING_CLUSTER_ID": "test-cluster-id"})
def test_upload_model_single_file(
    internal_teamspace_api_list_mocker,
    internal_user_api_mocker,
    tmp_path,
):
    ts = Teamspace("ts-abc", user="user-abc")

    with pytest.raises(FileNotFoundError):
        ts.upload_model(path=(tmp_path / "does-not-exist.ckpt"), name="user/modelname")

    # Upload single file
    file_path = tmp_path / "checkpoint.pt"
    file_path.touch()

    ts._teamspace_api.create_model = mock.Mock(return_value=mock.Mock(model_id="test-model-id", version="v3"))
    ts._teamspace_api.upload_model_file = mock.Mock()
    ts._teamspace_api.complete_model_upload = mock.Mock()

    result = ts.upload_model(path=str(file_path), name="modelname")

    ts._teamspace_api.create_model.assert_called_once_with(
        name="modelname",
        metadata={"filenames": "checkpoint.pt"},
        private=True,
        teamspace_id="ts-abc002",
        cloud_account="test-cluster-id",
    )
    ts._teamspace_api.upload_model_file.assert_called_with(
        model_id="test-model-id",
        version="v3",
        local_path=file_path,
        remote_path="checkpoint.pt",
        teamspace_id="ts-abc002",
        progress_bar=True,
    )
    ts._teamspace_api.complete_model_upload.assert_called_once()

    assert result.name == "modelname"
    assert result.version == "v3"
    assert result.teamspace == "ts-abc"
    assert result.cloud_account == "test-cluster-id"

    ts._teamspace_api.delete_model = mock.Mock()
    ts.delete_model("user/modelname")
    ts._teamspace_api.delete_model.assert_called_once_with(
        teamspace_id="ts-abc002",
        name="user/modelname",
        version="default",
    )


@mock.patch.dict(os.environ, {"LIGHTNING_CLUSTER_ID": "test-cluster-id"})
def test_upload_model_multiple_files(
    internal_teamspace_api_list_mocker,
    internal_user_api_mocker,
    tmp_path,
):
    ts = Teamspace("ts-abc", user="user-abc")

    # Attempt to upload empty folder raises error
    upload_path = tmp_path / "empty"
    (tmp_path / "empty" / "folder").mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="doesn't contain any files"):
        ts.upload_model(path=str(upload_path), name="user/modelname")

    # Upload nested folder of files
    upload_path = tmp_path / "checkpoint"
    upload_path.mkdir()
    (upload_path / "file").touch()
    (upload_path / "subfolder").mkdir()
    (upload_path / "subfolder" / "nested-file").touch()
    (upload_path / "empty").mkdir()  # empty folders don't get uploaded

    ts._teamspace_api.create_model = mock.Mock(return_value=mock.Mock(model_id="test-model-id", version="v3"))
    ts._teamspace_api.upload_model_file = mock.Mock()
    ts._teamspace_api.complete_model_upload = mock.Mock()

    ts.upload_model(path=str(upload_path), name="user/modelname")

    ts._teamspace_api.create_model.assert_called_once()
    assert ts._teamspace_api.upload_model_file.call_count == 2
    call_args = {
        "model_id": "test-model-id",
        "version": "v3",
        "teamspace_id": "ts-abc002",
        "progress_bar": True,
    }
    ts._teamspace_api.upload_model_file.assert_any_call(
        local_path=(upload_path / "file"),
        remote_path="file",
        **call_args,
    )
    ts._teamspace_api.upload_model_file.assert_any_call(
        local_path=(upload_path / "subfolder" / "nested-file"),
        remote_path="subfolder/nested-file",
        **call_args,
    )
    ts._teamspace_api.complete_model_upload.assert_called_once()

    ts._teamspace_api.delete_model = mock.Mock()
    ts.delete_model("user/modelname:v3")
    ts._teamspace_api.delete_model.assert_called_once_with(
        teamspace_id="ts-abc002",
        name="user/modelname",
        version="v3",
    )


@pytest.mark.parametrize("folder", ["download_dir", None])
@mock.patch("lightning_sdk.api.teamspace_api._download_model_files")
@mock.patch("lightning_sdk.api.teamspace_api._get_model_version")
def test_download_model(
    get_model_version_mock,
    download_model_files_mock,
    internal_teamspace_api_list_mocker,
    internal_user_api_mocker,
    tmp_path,
    monkeypatch,
    folder,
):
    monkeypatch.chdir(tmp_path)
    ts = Teamspace("ts-abc", user="user-abc")
    get_model_version_mock.return_value = V1ModelVersionArchive(
        model_id="model-id",
        version="v3",
        upload_complete=True,
    )
    download_model_files_mock.return_value = ["checkpoint/file.pt", "checkpoint/other"]

    result = ts.download_model("user/modelname", download_dir=folder)
    get_model_version_mock.assert_called_with(
        client=mock.ANY,
        teamspace_id="ts-abc002",
        name="user/modelname",
        version="default",
    )

    download_model_files_mock.assert_called_with(
        client=mock.ANY,
        teamspace_name="ts-abc",
        teamspace_owner_name="user-abc",
        name="user/modelname",
        version="default",
        download_dir=Path(folder) if folder else tmp_path,
        progress_bar=True,
    )
    assert result == str(tmp_path / folder if folder else tmp_path)


@mock.patch("lightning_sdk.api.teamspace_api._download_model_files")
@mock.patch("lightning_sdk.api.teamspace_api._get_model_version")
def test_download_model_version(
    get_model_version_mock,
    download_model_files_mock,
    internal_teamspace_api_list_mocker,
    internal_user_api_mocker,
    tmp_path,
):
    ts = Teamspace("ts-abc", user="user-abc")
    get_model_version_mock.return_value = V1ModelVersionArchive(
        model_id="model-id",
        version="v3",
        upload_complete=True,
    )

    ts.download_model("user/modelname:v3", download_dir=tmp_path)
    get_model_version_mock.assert_called_with(
        client=mock.ANY, teamspace_id="ts-abc002", name="user/modelname", version="v3"
    )
    download_model_files_mock.assert_called_with(
        client=mock.ANY,
        teamspace_name="ts-abc",
        teamspace_owner_name="user-abc",
        name="user/modelname",
        version="v3",
        download_dir=tmp_path,
        progress_bar=True,
    )


@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.list_jobs")
def test_list_jobs(
    list_jobs_mock,
    internal_get_org_api_mocker,
    internal_teamspace_api_mocker,
):
    from lightning_sdk.job.v1 import _JobV1
    from lightning_sdk.job.v2 import _JobV2

    apps = [Externalv1LightningappInstance(name="jobv1-1"), Externalv1LightningappInstance(name="jobv1-2")]
    jobs = [V1Job(name="jobv2-1"), V1Job(name="jobv2-2"), V1Job(name="jobv2-3")]
    ts = Teamspace("ts-abc", org="org-abc")

    list_jobs_mock.return_value = (apps, jobs)

    # it's important that there are no additional calls to fetch individual jobs here.
    # they'd raise API Errors since we only mock the teamspace APIs listing
    # and not individual fetch requests
    listed_jobs = ts.jobs

    assert len(listed_jobs) == 5
    assert all(isinstance(j, Job) for j in listed_jobs)

    for lj, aj in zip(listed_jobs, apps):
        assert lj.name == aj.name
        assert isinstance(lj._internal_job, _JobV1)

    for lj, jj in zip(listed_jobs[2:], jobs):
        assert lj.name == jj.name
        assert isinstance(lj._internal_job, _JobV2)


@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.list_mmts")
def test_list_mmts(list_mmts_mock, internal_get_org_api_mocker, internal_teamspace_api_mocker):
    from lightning_sdk.mmt.v1 import _MMTV1
    from lightning_sdk.mmt.v2 import _MMTV2

    apps = [Externalv1LightningappInstance(name="mmtv1-1"), Externalv1LightningappInstance(name="mmtv1-2")]
    mmts = [V1MultiMachineJob(name="mmtv2-1"), V1MultiMachineJob(name="mmtv2-2"), V1MultiMachineJob(name="mmtv2-3")]
    ts = Teamspace("ts-abc", org="org-abc")

    list_mmts_mock.return_value = (apps, mmts)

    # it's important that there are no additional calls to fetch individual mmts here.
    # they'd raise API Errors since we only mock the teamspace APIs listing
    # and not individual fetch requests
    listed_mmts = ts.multi_machine_jobs

    assert len(listed_mmts) == 5
    assert all(isinstance(j, MMT) for j in listed_mmts)

    for lj, aj in zip(listed_mmts, apps):
        assert lj.name == aj.name
        assert isinstance(lj._internal_mmt, _MMTV1)

    for lj, jj in zip(listed_mmts[2:], mmts):
        assert lj.name == jj.name
        assert isinstance(lj._internal_mmt, _MMTV2)


@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.teamspace._resolve_user")
@mock.patch("lightning_sdk.teamspace._resolve_org")
def test_list_machines(mock_resolve_org, mock_resolve_user, mock_teamspace_api):
    mock_teamspace_api().list_machines.return_value = [V1ClusterAccelerator(instance_id="instance-id")]
    mock_teamspace_api().get_teamspace().id = "teamspace-id"

    teamspace = Teamspace(name="teamspace-name")

    machines = teamspace.list_machines(cloud_account="cloud-account")

    assert len(machines) == 1
    assert machines[0].instance_type == "instance-id"

    mock_teamspace_api().list_machines.assert_called_once_with("teamspace-id", cloud_account="cloud-account")


@mock.patch.dict(os.environ, clear=True)
@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.teamspace._resolve_user")
@mock.patch("lightning_sdk.teamspace._resolve_org")
def test_list_machines_default_cloud_account(mock_resolve_org, mock_resolve_user, mock_teamspace_api):
    mock_teamspace_api().list_machines.return_value = [V1ClusterAccelerator(instance_id="instance-id")]
    mock_teamspace_api().get_teamspace().id = "teamspace-id"
    mock_teamspace_api().get_teamspace().project_settings.preferred_cluster = "preferred-cluster"

    teamspace = Teamspace(name="teamspace-name")

    machines = teamspace.list_machines()

    assert len(machines) == 1
    assert machines[0].instance_type == "instance-id"

    mock_teamspace_api().list_machines.assert_called_once_with("teamspace-id", cloud_account="preferred-cluster")


@mock.patch.dict(os.environ, {"LIGHTNING_CLUSTER_ID": "env-cloud-account"})
@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.teamspace._resolve_user")
@mock.patch("lightning_sdk.teamspace._resolve_org")
def test_list_machines_env_cloud_account(mock_resolve_org, mock_resolve_user, mock_teamspace_api):
    mock_teamspace_api().list_machines.return_value = [V1ClusterAccelerator(instance_id="instance-id")]
    mock_teamspace_api().get_teamspace().id = "teamspace-id"
    mock_teamspace_api().get_teamspace().project_settings.preferred_cluster = "preferred-cluster"

    teamspace = Teamspace(name="teamspace-name")

    machines = teamspace.list_machines()

    assert len(machines) == 1
    assert machines[0].instance_type == "instance-id"

    mock_teamspace_api().list_machines.assert_called_once_with("teamspace-id", cloud_account="env-cloud-account")
