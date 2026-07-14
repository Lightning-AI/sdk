import os
from contextlib import nullcontext
from pathlib import Path
from unittest import mock

import pytest

import lightning_sdk
from lightning_sdk.api.teamspace_api import SecretType
from lightning_sdk.job import Job
from lightning_sdk.lightning_cloud.openapi import (
    DataConnectionServiceCreateDataConnectionBody,
    V1AWSDirectV1,
    V1CloudProvider,
    V1ClusterAccelerator,
    V1ClusterType,
    V1EfsConfig,
    V1ExternalCluster,
    V1ExternalClusterSpec,
    V1Job,
    V1ListClustersResponse,
    V1ListMembershipsResponse,
    V1ListProjectClustersResponse,
    V1Membership,
    V1ModelVersionArchive,
    V1MultiMachineJob,
    V1Project,
    V1ProjectSettings,
    V1ProjectTab,
    V1R2DataConnection,
    V1Resources,
    V1S3FolderDataConnection,
)
from lightning_sdk.machine import Machine
from lightning_sdk.mmt import MMT
from lightning_sdk.organization import Organization
from lightning_sdk.teamspace import ConnectionType, Teamspace
from lightning_sdk.user import User


class MyDummyExperiment:
    def __init__(self, id: str) -> None:
        self.id = id


@pytest.mark.parametrize("user", ["user-abc", None, -1])
@pytest.mark.parametrize("org", ["org-abc", None, -1])
@mock.patch.dict(os.environ, clear=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
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
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
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
@mock.patch("lightning_sdk.lightning_cloud.login.Auth.authenticate", return_value="my-auth-header")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
@mock.patch(
    "lightning_sdk.api.teamspace_api.Auth",
    new=mock.MagicMock(return_value=mock.MagicMock(user_id="user-abc")),
)
def test_teamspace_list_clusters_studios_user(
    _mock_authenticate,
    internal_studio_api_list_mocker,
    internal_user_api_mocker,
    internal_teamspace_api_cluster_list_mocker,
    internal_teamspace_api_list_mocker,
):
    ts = Teamspace("ts-abc", user="user-abc")

    studios = ts.studios

    # 2 clusters * 3 studios per cluster
    assert len(studios) == 6


@mock.patch.dict(os.environ, clear=True)
@mock.patch("lightning_sdk.lightning_cloud.login.Auth.authenticate", return_value="my-auth-header")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
@mock.patch(
    "lightning_sdk.api.teamspace_api.Auth",
    new=mock.MagicMock(return_value=mock.MagicMock(user_id="user-abc")),
)
def test_teamspace_list_clusters_studios_org(
    _mock_authenticate,
    internal_studio_api_list_mocker,
    internal_get_org_api_mocker,
    internal_teamspace_api_cluster_list_mocker,
    internal_teamspace_api_list_mocker,
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
@mock.patch("lightning_sdk.lightning_cloud.login.Auth.authenticate", return_value="my-auth-header")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_repr(
    _mock_authenticate,
    internal_teamspace_api_list_mocker,
    internal_get_org_api_mocker,
    internal_user_api_mocker,
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
@mock.patch("lightning_sdk.lightning_cloud.login.Auth.authenticate", return_value="my-auth-header")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_str(
    _mock_authenticate,
    internal_teamspace_api_list_mocker,
    internal_get_org_api_mocker,
    internal_user_api_mocker,
    kwargs,
    expected,
):
    ts = Teamspace(name="ts-abc", **kwargs)
    assert str(ts) == expected


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_teamspace_error_user_and_org():
    with pytest.raises(
        ValueError, match="User and org are mutually exclusive. Please only specify the one who owns the teamspace."
    ):
        Teamspace(name="ts-abc", user="foo", org="bar")


@mock.patch("lightning_sdk.lightning_cloud.login.Auth.authenticate", return_value="my-auth-header")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_create_agent(
    _mock_authenticate,
    internal_teamspace_api_list_mocker,
    internal_user_api_mocker,
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
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
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
    ts._teamspace_api._complete_model_upload = mock.Mock()

    result = ts.upload_model(path=str(file_path), name="modelname", metadata={"weather": "sunny or rainy"})

    ts._teamspace_api.create_model.assert_called_once_with(
        name="modelname",
        version=None,
        metadata={"weather": "sunny or rainy", "lightning-sdk": lightning_sdk.__version__},
        private=True,
        teamspace_id="ts-abc002",
        cloud_account="test-cluster-id",
        experiment=None,
    )
    ts._teamspace_api.upload_model_file.assert_called_with(
        model_id="test-model-id",
        version="v3",
        local_path=file_path,
        remote_path="checkpoint.pt",
        teamspace_id="ts-abc002",
        progress_bar=True,
    )
    ts._teamspace_api._complete_model_upload.assert_called_once()

    assert result.name == "modelname"
    assert result.version == "v3"
    assert result.teamspace == "ts-abc"
    assert result.cloud_account == "test-cluster-id"

    ts._teamspace_api.delete_model = mock.Mock()
    ts.delete_model("user/modelname")
    ts._teamspace_api.delete_model.assert_called_once_with(
        teamspace_id="ts-abc002",
        name="user/modelname",
        version=None,
    )


@mock.patch.dict(os.environ, {"LIGHTNING_CLUSTER_ID": "test-cluster-id"})
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_upload_model_single_file_experiment(
    internal_teamspace_api_list_mocker,
    internal_user_api_mocker,
    tmp_path,
):
    ts = Teamspace("ts-abc", user="user-abc")

    dummy_experiment = MyDummyExperiment(id="exp_abc")

    with pytest.raises(FileNotFoundError):
        ts.upload_model(path=(tmp_path / "does-not-exist.ckpt"), name="user/modelname", experiment=dummy_experiment)

    # Upload single file
    file_path = tmp_path / "checkpoint.pt"
    file_path.touch()

    ts._teamspace_api.create_model = mock.Mock(return_value=mock.Mock(model_id="test-model-id", version="v3"))
    ts._teamspace_api.upload_model_file = mock.Mock()
    ts._teamspace_api._complete_model_upload = mock.Mock()

    result = ts.upload_model(
        path=str(file_path), name="modelname", metadata={"weather": "sunny or rainy"}, experiment=dummy_experiment
    )

    ts._teamspace_api.create_model.assert_called_once_with(
        name="modelname",
        version=None,
        metadata={"weather": "sunny or rainy", "lightning-sdk": lightning_sdk.__version__},
        private=True,
        teamspace_id="ts-abc002",
        cloud_account="test-cluster-id",
        experiment=dummy_experiment,
    )
    ts._teamspace_api.upload_model_file.assert_called_with(
        model_id="test-model-id",
        version="v3",
        local_path=file_path,
        remote_path="checkpoint.pt",
        teamspace_id="ts-abc002",
        progress_bar=True,
    )
    ts._teamspace_api._complete_model_upload.assert_called_once()

    assert result.name == "modelname"
    assert result.version == "v3"
    assert result.teamspace == "ts-abc"
    assert result.cloud_account == "test-cluster-id"

    ts._teamspace_api.delete_model = mock.Mock()
    ts.delete_model("user/modelname")
    ts._teamspace_api.delete_model.assert_called_once_with(
        teamspace_id="ts-abc002",
        name="user/modelname",
        version=None,
    )


@mock.patch.dict(os.environ, {"LIGHTNING_CLUSTER_ID": "test-cluster-id"})
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
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
    ts._teamspace_api._complete_model_upload = mock.Mock()

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
    ts._teamspace_api._complete_model_upload.assert_called_once()

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
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
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
        version=None,
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
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
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
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_list_jobs(
    list_jobs_mock,
    internal_get_org_api_mocker,
    internal_teamspace_api_mocker,
    internal_user_api_mocker,
):
    jobs = [V1Job(name="jobv2-1"), V1Job(name="jobv2-2"), V1Job(name="jobv2-3")]
    ts = Teamspace("ts-abc", org="org-abc")

    list_jobs_mock.return_value = jobs

    # it's important that there are no additional calls to fetch individual jobs here.
    # they'd raise API Errors since we only mock the teamspace APIs listing
    # and not individual fetch requests
    listed_jobs = ts.jobs

    assert len(listed_jobs) == 3
    assert all(isinstance(j, Job) for j in listed_jobs)

    for lj, jj in zip(listed_jobs, jobs):
        assert lj.name == jj.name
        assert lj._job is jj


@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.list_mmts")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_list_mmts(
    list_mmts_mock,
    internal_get_org_api_mocker,
    internal_teamspace_api_mocker,
    internal_user_api_mocker,
):
    mmts = [V1MultiMachineJob(name="mmtv2-1"), V1MultiMachineJob(name="mmtv2-2"), V1MultiMachineJob(name="mmtv2-3")]
    ts = Teamspace("ts-abc", org="org-abc")

    list_mmts_mock.return_value = mmts

    # it's important that there are no additional calls to fetch individual mmts here.
    # they'd raise API Errors since we only mock the teamspace APIs listing
    # and not individual fetch requests
    listed_mmts = ts.multi_machine_jobs

    assert len(listed_mmts) == 3
    assert all(isinstance(j, MMT) for j in listed_mmts)

    for lj, jj in zip(listed_mmts, mmts):
        assert lj.name == jj.name
        assert lj._job is jj


@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.teamspace._resolve_user")
@mock.patch("lightning_sdk.teamspace._resolve_org")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_list_machines(mock_resolve_org, mock_resolve_user, mock_teamspace_api):
    mock_teamspace_api().list_machines.return_value = [
        V1ClusterAccelerator(
            instance_id="instance-id", slug="t4-x-2", slug_multi_cloud="lit-t4-2", resources=V1Resources(cpu=4, gpu=2)
        )
    ]
    mock_teamspace_api().get_teamspace().id = "teamspace-id"
    mock_org = mock_resolve_org.return_value
    mock_org.id = None

    teamspace = Teamspace(name="teamspace-name")

    machines = teamspace.list_machines(cloud_account="cloud-account")

    assert len(machines) == 1
    assert machines[0].instance_type == "instance-id"
    assert machines[0].accelerator_count == 2

    mock_teamspace_api().list_machines.assert_called_once_with(
        "teamspace-id", cloud_accounts=["cloud-account"], machine=None, org_id=None
    )


@mock.patch.dict(os.environ, clear=True)
@mock.patch("lightning_sdk.teamspace.CloudAccountApi")
@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.teamspace._resolve_user")
@mock.patch("lightning_sdk.teamspace._resolve_org")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_list_machines_global_cloud_account(
    mock_resolve_org, mock_resolve_user, mock_teamspace_api, mock_cloud_account_api
):
    mock_cloud_account_1 = mock.MagicMock()
    mock_cloud_account_1.id = "global-cloud-account-1"
    mock_cloud_account_2 = mock.MagicMock()
    mock_cloud_account_2.id = "global-cloud-account-2"

    mock_cloud_account_api().list_global_cloud_accounts.return_value = [mock_cloud_account_1, mock_cloud_account_2]

    mock_org = mock_resolve_org.return_value
    mock_org.id = None

    mock_teamspace_api().list_machines.return_value = [
        V1ClusterAccelerator(
            instance_id="instance-id", slug="t4-x-2", slug_multi_cloud="lit-t4-2", resources=V1Resources(cpu=4, gpu=2)
        )
    ]
    mock_teamspace_api().get_teamspace().id = "teamspace-id"

    teamspace = Teamspace(name="teamspace-name")

    machines = teamspace.list_machines()

    assert len(machines) == 1
    assert machines[0].instance_type == "instance-id"
    assert machines[0].accelerator_count == 2

    mock_teamspace_api().list_machines.assert_called_once_with(
        "teamspace-id", cloud_accounts=["global-cloud-account-1", "global-cloud-account-2"], machine=None, org_id=None
    )


@mock.patch.dict(os.environ, {"LIGHTNING_CLUSTER_ID": "env-cloud-account"})
@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.teamspace._resolve_user")
@mock.patch("lightning_sdk.teamspace._resolve_org")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_list_machines_env_cloud_account(mock_resolve_org, mock_resolve_user, mock_teamspace_api):
    mock_teamspace_api().list_machines.return_value = [
        V1ClusterAccelerator(
            instance_id="instance-id", slug="t4-x-2", slug_multi_cloud="lit-t4-2", resources=V1Resources(cpu=4, gpu=2)
        )
    ]
    mock_teamspace_api().get_teamspace().id = "teamspace-id"
    mock_teamspace_api().get_teamspace().project_settings.preferred_cluster = "preferred-cluster"
    mock_org = mock_resolve_org.return_value
    mock_org.id = None

    teamspace = Teamspace(name="teamspace-name")

    machines = teamspace.list_machines()

    assert len(machines) == 1
    assert machines[0].instance_type == "instance-id"
    assert machines[0].accelerator_count == 2

    mock_teamspace_api().list_machines.assert_called_once_with(
        "teamspace-id", cloud_accounts=["env-cloud-account"], machine=None, org_id=None
    )


@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.teamspace.CloudAccountApi")
@mock.patch("lightning_sdk.teamspace._resolve_user")
@mock.patch("lightning_sdk.teamspace._resolve_org")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_list_machines_with_machine_filter(
    mock_resolve_org, mock_resolve_user, mock_cloud_account_api, mock_teamspace_api
):
    mock_teamspace_api().list_machines.return_value = [
        V1ClusterAccelerator(
            instance_id="instance-id",
            slug="h100-x-8",
            slug_multi_cloud="lit-h100-8",
            resources=V1Resources(cpu=0, gpu=8),
        )
    ]
    mock_teamspace_api().get_teamspace().id = "teamspace-id"

    mock_org = mock_resolve_org.return_value
    mock_org.id = "org-id"

    teamspace = Teamspace(name="teamspace-name")
    machines = teamspace.list_machines(cloud_account="cloud-account", machine="H100_X_8")

    assert len(machines) == 1
    assert machines[0].instance_type == "instance-id"

    call_args = mock_teamspace_api().list_machines.call_args
    assert call_args[0][0] == "teamspace-id"
    assert call_args[1]["cloud_accounts"] == ["cloud-account"]
    assert call_args[1]["org_id"] == mock_org.id
    assert call_args[1]["machine"] is not None
    assert isinstance(call_args[1]["machine"], Machine)


@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.teamspace.CloudAccountApi")
@mock.patch("lightning_sdk.teamspace._resolve_user")
@mock.patch("lightning_sdk.teamspace._resolve_org")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_list_machines_with_invalid_machine(
    mock_resolve_org, mock_resolve_user, mock_cloud_account_api, mock_teamspace_api
):
    mock_teamspace_api().get_teamspace().id = "teamspace-id"

    mock_org = mock_resolve_org.return_value
    mock_org.id = "org-id"

    teamspace = Teamspace(name="teamspace-name")

    with pytest.raises(ValueError, match="Machine 'invalid-machine' is not valid"):
        teamspace.list_machines(cloud_account="cloud-account", machine="invalid-machine")

    mock_teamspace_api().list_machines.assert_not_called()


@pytest.mark.parametrize(
    ("teamspace_preferred_cluster", "org_default_cloud_account", "expected_result"),
    [
        # Preferred cluster takes precedence
        ("teamspace-cluster", "org-cluster", "teamspace-cluster"),
        ("teamspace-cluster", None, "teamspace-cluster"),
        # Fallback to org default if no preferred cluster
        (None, "org-cluster", "org-cluster"),
        ("", "org-cluster", "org-cluster"),
        # No preferred cluster and no org default
        (None, None, None),
        ("", None, None),
        # Empty string from org is returned as-is if preferred_cluster is falsy
        ("", "", ""),
    ],
)
@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.teamspace._resolve_user")
@mock.patch("lightning_sdk.teamspace._resolve_org")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_teamspace_default_cloud_account_resolution(
    mock_resolve_org,
    mock_resolve_user,
    mock_teamspace_api,
    teamspace_preferred_cluster,
    org_default_cloud_account,
    expected_result,
):
    """Test that Teamspace.default_cloud_account resolves correctly with teamspace preferred_cluster and org fallback"""

    # Set up mock for preferred_cluster
    mock_teamspace_api().get_teamspace().project_settings.preferred_cluster = teamspace_preferred_cluster

    # Set up org mock (only relevant fallback owner type)
    mock_org = mock.Mock(spec=Organization)
    mock_org.default_cloud_account = org_default_cloud_account
    mock_resolve_org.return_value = mock_org if org_default_cloud_account is not None else None

    # Always pass org as owner since only org is relevant here
    teamspace = Teamspace(name="teamspace-name", org="test-org")

    assert teamspace.default_cloud_account == expected_result


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_teamspace_secrets_property(
    internal_teamspace_api_list_mocker,
    internal_user_api_mocker,
):
    ts = Teamspace("ts-abc", user="user-abc")

    mock_secrets = {"API_KEY": "***REDACTED***", "DATABASE_URL": "***REDACTED***"}

    with mock.patch.object(ts._teamspace_api, "get_secrets", return_value=mock_secrets) as mock_get:
        secrets = ts.secrets

    assert secrets == mock_secrets
    mock_get.assert_called_once_with("ts-abc002")


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_teamspace_set_secret(
    internal_teamspace_api_list_mocker,
    internal_user_api_mocker,
):
    ts = Teamspace("ts-abc", user="user-abc")

    with mock.patch.object(ts._teamspace_api, "set_secret") as mock_set:
        ts.set_secret("NEW_SECRET", "secret_value")

    mock_set.assert_called_once_with("ts-abc002", "NEW_SECRET", "secret_value", secret_type=SecretType.GENERIC)


@pytest.mark.parametrize("secret_type", [SecretType.HF_TOKEN, "hf_token"])
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_teamspace_set_secret_hf_token(
    internal_teamspace_api_list_mocker,
    internal_user_api_mocker,
    secret_type,
):
    ts = Teamspace("ts-abc", user="user-abc")

    with mock.patch.object(ts._teamspace_api, "set_secret") as mock_set:
        ts.set_secret("HF_TOKEN", "hf_xxx", secret_type=secret_type)

    mock_set.assert_called_once_with("ts-abc002", "HF_TOKEN", "hf_xxx", secret_type=secret_type)


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_teamspace_set_secret_invalid_name(
    internal_teamspace_api_list_mocker,
    internal_user_api_mocker,
):
    ts = Teamspace("ts-abc", user="user-abc")

    with pytest.raises(
        ValueError,
        match="Secret keys must only contain alphanumeric characters and underscores and not begin with a number.",
    ):
        ts.set_secret("123_INVALID", "secret_value")


@mock.patch("lightning_sdk.api.teamspace_api.LightningClient")
@mock.patch("lightning_sdk.api.cloud_account_api.LightningClient")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_new_folder_agnostic(
    mock_cloud_account_client,
    mock_teamspace_client,
    internal_user_api_mocker,
):
    mock_teamspace_client().projects_service_list_memberships.return_value = V1ListMembershipsResponse(
        [
            V1Membership(
                name="ts-abc", display_name="ts-abc", project_id="ts-abc002", owner_id="user-abc", owner_type="user"
            ),
        ],
    )

    mock_teamspace_client().projects_service_get_project.return_value = V1Project(
        id="ts-abc002",
        name="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="aws-cluster"),
        owner_id="user-abc",
        owner_type="user",
    )

    ts = Teamspace("ts-abc", user="user-abc")

    mock_project_response = V1ListProjectClustersResponse(
        clusters=[
            V1ExternalCluster(
                id="aws-cluster",
                spec=V1ExternalClusterSpec(driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.GLOBAL),
            ),
            V1ExternalCluster(
                id="gcp-cluster",
                spec=V1ExternalClusterSpec(driver=V1CloudProvider.GCP, cluster_type=V1ClusterType.GLOBAL),
            ),
        ]
    )
    mock_global_response = V1ListClustersResponse(clusters=[])
    mock_cloud_account_client.return_value.cluster_service_list_project_clusters.return_value = mock_project_response
    mock_cloud_account_client.return_value.cluster_service_list_clusters.return_value = mock_global_response

    mock_teamspace_client.return_value.data_connection_service_create_data_connection = mock.MagicMock()

    ts.new_folder("test-folder")

    mock_teamspace_client.return_value.data_connection_service_create_data_connection.assert_called_once_with(
        DataConnectionServiceCreateDataConnectionBody(
            name="test-folder",
            create_resources=True,
            force=True,
            writable=True,
            r2=V1R2DataConnection(name="test-folder"),
        ),
        ts.id,
    )


@mock.patch("lightning_sdk.api.teamspace_api.LightningClient")
@mock.patch("lightning_sdk.api.cloud_account_api.LightningClient")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_new_folder_byoc(
    mock_cloud_account_client,
    mock_teamspace_client,
    internal_user_api_mocker,
):
    mock_teamspace_client().projects_service_list_memberships.return_value = V1ListMembershipsResponse(
        [
            V1Membership(
                name="ts-abc", display_name="ts-abc", project_id="ts-abc002", owner_id="user-abc", owner_type="user"
            ),
        ],
    )

    mock_teamspace_client().projects_service_get_project.return_value = V1Project(
        id="ts-abc002",
        name="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="aws-cluster"),
        owner_id="user-abc",
        owner_type="user",
    )

    ts = Teamspace("ts-abc", user="user-abc")

    mock_project_response = V1ListProjectClustersResponse(
        clusters=[
            V1ExternalCluster(
                id="aws-cluster",
                spec=V1ExternalClusterSpec(driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.GLOBAL),
            ),
            V1ExternalCluster(
                id="gcp-cluster",
                spec=V1ExternalClusterSpec(driver=V1CloudProvider.GCP, cluster_type=V1ClusterType.GLOBAL),
            ),
            V1ExternalCluster(
                id="byoc-cluster",
                spec=V1ExternalClusterSpec(
                    driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.BYOC, aws_v1=V1AWSDirectV1()
                ),
            ),
        ]
    )
    mock_global_response = V1ListClustersResponse(clusters=[])
    mock_cloud_account_client.return_value.cluster_service_list_project_clusters.return_value = mock_project_response
    mock_cloud_account_client.return_value.cluster_service_list_clusters.return_value = mock_global_response

    mock_teamspace_client.return_value.data_connection_service_create_data_connection = mock.MagicMock()

    ts.new_folder("test-folder", cloud_account="byoc-cluster")

    mock_teamspace_client.return_value.data_connection_service_create_data_connection.assert_called_once_with(
        DataConnectionServiceCreateDataConnectionBody(
            name="test-folder",
            create_resources=True,
            force=True,
            writable=True,
            s3_folder=V1S3FolderDataConnection(),
            cluster_id="byoc-cluster",
            access_cluster_ids=["byoc-cluster"],
        ),
        ts.id,
    )


@pytest.mark.parametrize("writable", [True, False])
@mock.patch("lightning_sdk.api.teamspace_api.LightningClient")
@mock.patch("lightning_sdk.api.cloud_account_api.LightningClient")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_new_connection_efs(mock_cloud_account_client, mock_teamspace_client, internal_user_api_mocker, writable):
    mock_teamspace_client().projects_service_list_memberships.return_value = V1ListMembershipsResponse(
        [
            V1Membership(
                name="ts-abc", display_name="ts-abc", project_id="ts-abc002", owner_id="user-abc", owner_type="user"
            ),
        ],
    )

    mock_teamspace_client().projects_service_get_project.return_value = V1Project(
        id="ts-abc002",
        name="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="aws-cluster"),
        owner_id="user-abc",
        owner_type="user",
    )

    ts = Teamspace("ts-abc", user="user-abc")

    mock_project_response = V1ListProjectClustersResponse(
        clusters=[
            V1ExternalCluster(
                id="aws-cluster",
                spec=V1ExternalClusterSpec(driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.GLOBAL),
            ),
            V1ExternalCluster(
                id="gcp-cluster",
                spec=V1ExternalClusterSpec(driver=V1CloudProvider.GCP, cluster_type=V1ClusterType.GLOBAL),
            ),
            V1ExternalCluster(
                id="byoc-cluster",
                spec=V1ExternalClusterSpec(
                    driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.BYOC, aws_v1=V1AWSDirectV1()
                ),
            ),
        ]
    )
    mock_global_response = V1ListClustersResponse(clusters=[])
    mock_cloud_account_client.return_value.cluster_service_list_project_clusters.return_value = mock_project_response
    mock_cloud_account_client.return_value.cluster_service_list_clusters.return_value = mock_global_response

    mock_teamspace_client.return_value.data_connection_service_create_data_connection = mock.MagicMock()

    ts.new_connection(
        name="test-connection-efs",
        source="efs-filesystem-id",
        connection_type=ConnectionType.EFS,
        region="us-east-2",
        writable=writable,
    )

    mock_teamspace_client.return_value.data_connection_service_create_data_connection.assert_called_once_with(
        DataConnectionServiceCreateDataConnectionBody(
            name="test-connection-efs",
            create_resources=False,
            force=True,
            writable=writable,
            efs=V1EfsConfig(file_system_id="efs-filesystem-id", region="us-east-2"),
            cluster_id="byoc-cluster",
            access_cluster_ids=["byoc-cluster"],
        ),
        ts.id,
    )


# Permission tests for Teamspace resource access
@pytest.fixture(autouse=True)
def _clear_teamspace_permission_cache():
    """Clear the permission cache before each test."""
    from lightning_sdk.api.utils import allowed_resource_access

    allowed_resource_access.cache_clear()
    yield
    allowed_resource_access.cache_clear()


@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@mock.patch("lightning_sdk.teamspace._resolve_user")
@pytest.mark.project_permission_test()
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_teamspace_studios_property_when_allowed(mock_resolve_user, mock_teamspace_api, mock_teamspace_api_module):
    """Test that Teamspace.studios succeeds when Studios permission is allowed."""
    mock_user = mock.Mock(spec=User)
    mock_user.name = "test-user"
    mock_resolve_user.return_value = mock_user

    # Mock the teamspace with Studios enabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="studio", is_enabled=True)],
    )
    # Mock get_teamspace to return the project directly, bypassing list_teamspaces
    mock_teamspace_api_module.return_value.get_teamspace = mock.Mock(return_value=mock_project)
    mock_teamspace_api_module.return_value.list_teamspaces.return_value = [mock_project]

    mock_teamspace_api_module.return_value._get_teamspace_by_id.return_value = mock_project

    # Mock _get_authed_user_id to prevent authentication calls
    mock_teamspace_api_module.return_value._get_authed_user_id.return_value = "test-user-id"

    # Mock cloud accounts and studios lists
    from lightning_sdk.lightning_cloud.openapi import V1ProjectClusterBinding

    mock_cloud_account = V1ProjectClusterBinding(cluster_id="cluster-1", cluster_name="cluster-1")
    mock_teamspace_api_module.return_value.list_cloud_accounts.return_value = [mock_cloud_account]
    mock_teamspace_api_module.return_value.list_studios.return_value = []

    ts = Teamspace("test-teamspace", user="test-user")

    # Should not raise
    studios = ts.studios
    assert isinstance(studios, list)


@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@mock.patch("lightning_sdk.teamspace._resolve_user")
@pytest.mark.project_permission_test()
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_teamspace_studios_property_when_denied(mock_resolve_user, mock_teamspace_api, mock_teamspace_api_module):
    """Test that Teamspace.studios raises PermissionError when Studios permission is denied."""
    mock_user = mock.Mock(spec=User)
    mock_user.name = "test-user"
    mock_resolve_user.return_value = mock_user

    # Mock the teamspace with Studios disabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="studio", is_enabled=False)],
    )
    # Mock get_teamspace to return the project directly, bypassing list_teamspaces
    mock_teamspace_api_module.return_value.get_teamspace = mock.Mock(return_value=mock_project)
    mock_teamspace_api_module.return_value.list_teamspaces.return_value = [mock_project]

    mock_teamspace_api_module.return_value._get_teamspace_by_id.return_value = mock_project
    # Also mock the TeamspaceApi used by allowed_resource_access
    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_project

    # Mock _get_authed_user_id to prevent authentication calls
    mock_teamspace_api_module.return_value._get_authed_user_id.return_value = "test-user-id"

    ts = Teamspace("test-teamspace", user="test-user")

    with pytest.raises(PermissionError, match="Access to Studios has been disabled"):
        _ = ts.studios


@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@mock.patch("lightning_sdk.teamspace._resolve_user")
@pytest.mark.project_permission_test()
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_teamspace_jobs_property_when_allowed(mock_resolve_user, mock_teamspace_api, mock_teamspace_api_module):
    """Test that Teamspace.jobs succeeds when Jobs permission is allowed."""
    mock_user = mock.Mock(spec=User)
    mock_user.name = "test-user"
    mock_resolve_user.return_value = mock_user

    # Mock the teamspace with Jobs enabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="jobs", is_enabled=True)],
    )
    # Mock get_teamspace to return the project directly, bypassing list_teamspaces
    mock_teamspace_api_module.return_value.get_teamspace = mock.Mock(return_value=mock_project)
    mock_teamspace_api_module.return_value.list_teamspaces.return_value = [mock_project]

    mock_teamspace_api_module.return_value._get_teamspace_by_id.return_value = mock_project

    # Mock _get_authed_user_id to prevent authentication calls
    mock_teamspace_api_module.return_value._get_authed_user_id.return_value = "test-user-id"

    # Mock empty job list response
    mock_teamspace_api_module.return_value.list_jobs.return_value = []

    ts = Teamspace("test-teamspace", user="test-user")

    # Should not raise
    jobs = ts.jobs
    assert isinstance(jobs, tuple)


@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@mock.patch("lightning_sdk.teamspace._resolve_user")
@pytest.mark.project_permission_test()
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_teamspace_jobs_property_when_denied(mock_resolve_user, mock_teamspace_api, mock_teamspace_api_module):
    """Test that Teamspace.jobs raises PermissionError when Jobs permission is denied."""
    mock_user = mock.Mock(spec=User)
    mock_user.name = "test-user"
    mock_resolve_user.return_value = mock_user

    # Mock the teamspace with Jobs disabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="jobs", is_enabled=False)],
    )
    # Mock get_teamspace to return the project directly, bypassing list_teamspaces
    mock_teamspace_api_module.return_value.get_teamspace = mock.Mock(return_value=mock_project)
    mock_teamspace_api_module.return_value.list_teamspaces.return_value = [mock_project]

    mock_teamspace_api_module.return_value._get_teamspace_by_id.return_value = mock_project
    # Also mock the TeamspaceApi used by allowed_resource_access
    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_project

    # Mock _get_authed_user_id to prevent authentication calls
    mock_teamspace_api_module.return_value._get_authed_user_id.return_value = "test-user-id"

    ts = Teamspace("test-teamspace", user="test-user")

    with pytest.raises(PermissionError, match="Access to Jobs has been disabled"):
        _ = ts.jobs


@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@mock.patch("lightning_sdk.teamspace._resolve_user")
@pytest.mark.project_permission_test()
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_teamspace_multi_machine_jobs_property_when_allowed(
    mock_resolve_user, mock_teamspace_api, mock_teamspace_api_module
):
    """Test that Teamspace.multi_machine_jobs succeeds when Jobs permission is allowed."""
    mock_user = mock.Mock(spec=User)
    mock_user.name = "test-user"
    mock_resolve_user.return_value = mock_user

    # Mock the teamspace with Jobs enabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="jobs", is_enabled=True)],
    )
    # Mock get_teamspace to return the project directly, bypassing list_teamspaces
    mock_teamspace_api_module.return_value.get_teamspace = mock.Mock(return_value=mock_project)
    mock_teamspace_api_module.return_value.list_teamspaces.return_value = [mock_project]

    mock_teamspace_api_module.return_value._get_teamspace_by_id.return_value = mock_project

    # Mock _get_authed_user_id to prevent authentication calls
    mock_teamspace_api_module.return_value._get_authed_user_id.return_value = "test-user-id"

    # Mock empty MMT list response
    mock_teamspace_api_module.return_value.list_mmts.return_value = []

    ts = Teamspace("test-teamspace", user="test-user")

    # Should not raise
    mmts = ts.multi_machine_jobs
    assert isinstance(mmts, tuple)


@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@mock.patch("lightning_sdk.teamspace._resolve_user")
@pytest.mark.project_permission_test()
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_teamspace_multi_machine_jobs_property_when_denied(
    mock_resolve_user, mock_teamspace_api, mock_teamspace_api_module
):
    """Test that Teamspace.multi_machine_jobs raises PermissionError when Jobs permission is denied."""
    mock_user = mock.Mock(spec=User)
    mock_user.name = "test-user"
    mock_resolve_user.return_value = mock_user

    # Mock the teamspace with Jobs disabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="jobs", is_enabled=False)],
    )
    # Mock get_teamspace to return the project directly, bypassing list_teamspaces
    mock_teamspace_api_module.return_value.get_teamspace = mock.Mock(return_value=mock_project)
    mock_teamspace_api_module.return_value.list_teamspaces.return_value = [mock_project]

    mock_teamspace_api_module.return_value._get_teamspace_by_id.return_value = mock_project
    # Also mock the TeamspaceApi used by allowed_resource_access
    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_project

    # Mock _get_authed_user_id to prevent authentication calls
    mock_teamspace_api_module.return_value._get_authed_user_id.return_value = "test-user-id"

    ts = Teamspace("test-teamspace", user="test-user")

    with pytest.raises(PermissionError, match="Access to Jobs has been disabled"):
        _ = ts.multi_machine_jobs


@mock.patch.dict(os.environ, {"LIGHTNING_CLOUD_URL": "https://lightning.ai", "LIGHTNING_AUTH_TOKEN": "test-token"})
@mock.patch("lightning_sdk.lightning_cloud.utils.dataset.LightningClient")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_download_dataset_version(
    mock_lightning_client,
    internal_teamspace_api_list_mocker,
    internal_user_api_mocker,
):
    import json
    import urllib

    from lightning_sdk.lightning_cloud.utils.dataset import _download_dataset_version

    mock_list_response = mock.MagicMock()
    mock_list_response.data = json.dumps({"datasets": []})

    mock_files_response = mock.MagicMock()
    mock_files_response.data = json.dumps(
        {"files": [{"filepath": "data.csv", "url": "https://presigned.example.com/data.csv"}]}
    )

    mock_api_client = mock.MagicMock()
    mock_api_client.request.side_effect = [mock_list_response, mock_files_response]
    mock_api_client.default_headers = {"Authorization": "Bearer test"}

    mock_client_instance = mock.MagicMock()
    mock_client_instance.api_client = mock_api_client
    mock_lightning_client.return_value = mock_client_instance

    target_path = "/tmp/test_dataset_download.zip"
    try:
        with mock.patch.object(urllib.request, "urlretrieve", return_value=None) as mock_urlretrieve, mock.patch(
            "shutil.make_archive"
        ) as mock_make_archive:
            _download_dataset_version(
                project_id="proj-1",
                dataset_name="ds-1",
                version="3",
                target_path=target_path,
                cluster_id="aws-us-east",
            )

        mock_api_client.request.assert_any_call(
            "GET",
            "https://lightning.ai/v1/projects/proj-1/lit-datasets",
            headers=mock.ANY,
            _preload_content=True,
        )
        mock_api_client.request.assert_any_call(
            "GET",
            "https://lightning.ai/v1/projects/proj-1/lit-datasets/ds-1/versions/3/files",
            query_params={"clusterId": "aws-us-east"},
            headers=mock.ANY,
            _preload_content=True,
        )
        mock_urlretrieve.assert_called_once_with("https://presigned.example.com/data.csv", mock.ANY)
        mock_make_archive.assert_called_once_with("/tmp/test_dataset_download", "zip", mock.ANY)
    finally:
        if os.path.exists(target_path):
            os.unlink(target_path)


@mock.patch.dict(os.environ, {"LIGHTNING_CLOUD_URL": "https://lightning.ai"})
@mock.patch("lightning_sdk.lightning_cloud.utils.dataset.LightningClient")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_download_dataset_version_no_token_no_cluster(
    mock_lightning_client,
    internal_teamspace_api_list_mocker,
    internal_user_api_mocker,
):
    import json
    import urllib

    from lightning_sdk.lightning_cloud.utils.dataset import _download_dataset_version

    mock_list_response = mock.MagicMock()
    mock_list_response.data = json.dumps({"datasets": []})

    mock_files_response = mock.MagicMock()
    mock_files_response.data = json.dumps(
        {"files": [{"filepath": "data.csv", "url": "https://presigned.example.com/data.csv"}]}
    )

    mock_api_client = mock.MagicMock()
    mock_api_client.request.side_effect = [mock_list_response, mock_files_response]
    mock_api_client.default_headers = {}

    mock_client_instance = mock.MagicMock()
    mock_client_instance.api_client = mock_api_client
    mock_lightning_client.return_value = mock_client_instance

    target_path = "/tmp/test_ds_no_token.zip"
    try:
        with mock.patch.object(urllib.request, "urlretrieve", return_value=None) as mock_urlretrieve, mock.patch(
            "shutil.make_archive"
        ) as mock_make_archive:
            _download_dataset_version(
                project_id="proj-1",
                dataset_name="ds-2",
                version="1",
                target_path=target_path,
            )

        mock_api_client.request.assert_any_call(
            "GET",
            "https://lightning.ai/v1/projects/proj-1/lit-datasets",
            headers=mock.ANY,
            _preload_content=True,
        )
        mock_api_client.request.assert_any_call(
            "GET",
            "https://lightning.ai/v1/projects/proj-1/lit-datasets/ds-2/versions/1/files",
            query_params={},
            headers=mock.ANY,
            _preload_content=True,
        )
        mock_urlretrieve.assert_called_once_with("https://presigned.example.com/data.csv", mock.ANY)
        mock_make_archive.assert_called_once_with("/tmp/test_ds_no_token", "zip", mock.ANY)
    finally:
        if os.path.exists(target_path):
            os.unlink(target_path)
