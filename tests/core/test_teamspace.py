from lightning_sdk.user import User
from lightning_sdk.organization import Organization
from lightning_sdk.teamspace import Teamspace
import pytest
import os
from unittest import mock
from contextlib import nullcontext
from pathlib import Path


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
    "kwargs,expected",
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
    "kwargs,expected",
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

    result = ts.upload_model(path=file_path, name="user/modelname")

    ts._teamspace_api.create_model.assert_called_once()
    ts._teamspace_api.upload_model_file.assert_called_with(
        model_id="test-model-id",
        version="v3",
        local_path=file_path,
        remote_path="checkpoint.pt",
        cluster_id="test-cluster-id",
        teamspace_id="ts-abc002",
        progress_bar=True,
    )
    ts._teamspace_api.complete_model_upload.assert_called_once()

    assert result.name == "user/modelname"
    assert result.version == "v3"
    assert result.teamspace == "ts-abc"
    assert result.cluster == "test-cluster-id"


@mock.patch.dict(os.environ, {"LIGHTNING_CLUSTER_ID": "test-cluster-id"})
def test_upload_model_multiple_files(
    internal_teamspace_api_list_mocker,
    internal_user_api_mocker,
    tmp_path,
):
    ts = Teamspace("ts-abc", user="user-abc")

    # Attempt to upload empty folder raises error
    root_path = tmp_path / "empty"
    (tmp_path / "empty" / "folder").mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="doesn't contain any files"):
        ts.upload_model(path=root_path, name="user/modelname")

    # Upload nested folder of files
    root_path = tmp_path / "checkpoint"
    root_path.mkdir()
    (root_path / "file").touch()
    (root_path / "subfolder").mkdir()
    (root_path / "subfolder" / "nested-file").touch()
    (root_path / "empty").mkdir()  # empty folders don't get uploaded

    ts._teamspace_api.create_model = mock.Mock(return_value=mock.Mock(model_id="test-model-id", version="v3"))
    ts._teamspace_api.upload_model_file = mock.Mock()
    ts._teamspace_api.complete_model_upload = mock.Mock()

    ts.upload_model(path=root_path, name="user/modelname")

    ts._teamspace_api.create_model.assert_called_once()
    assert ts._teamspace_api.upload_model_file.call_count == 2
    call_args = dict(
        model_id="test-model-id",
        version="v3",
        cluster_id="test-cluster-id",
        teamspace_id="ts-abc002",
        progress_bar=True,
    )
    ts._teamspace_api.upload_model_file.assert_any_call(
        local_path=(root_path / "file"),
        remote_path="checkpoint/file",
        **call_args,
    )
    ts._teamspace_api.upload_model_file.assert_any_call(
        local_path=(root_path / "subfolder" / "nested-file"),
        remote_path="checkpoint/subfolder/nested-file",
        **call_args,
    )
    ts._teamspace_api.complete_model_upload.assert_called_once()


@mock.patch("lightning_sdk.api.teamspace_api._download_model_files")
def test_download_model(
    download_model_files_mock,
    internal_teamspace_api_list_mocker,
    internal_user_api_mocker,
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    ts = Teamspace("ts-abc", user="user-abc")
    download_model_files_mock.return_value = ["checkpoint/file.pt", "checkpoint/other"]

    # download_dir default (current working directory)
    result = ts.download_model("user/modelname")
    download_model_files_mock.assert_called_with(
        client=mock.ANY,
        teamspace_id="ts-abc002",
        name="user/modelname",
        version="latest",
        download_dir=tmp_path,
        progress_bar=True,
    )
    assert result == str(tmp_path / "checkpoint")

    # download_dir specified
    download_dir = "download_dir"
    result = ts.download_model("user/modelname", download_dir=download_dir)
    download_model_files_mock.assert_called_with(
        client=mock.ANY,
        teamspace_id="ts-abc002",
        name="user/modelname",
        version="latest",
        download_dir=Path(download_dir),
        progress_bar=True,
    )
    assert result == str(tmp_path / download_dir / "checkpoint")


@mock.patch("lightning_sdk.api.teamspace_api._download_model_files")
def test_download_model_version(
    download_model_files_mock,
    internal_teamspace_api_list_mocker,
    internal_user_api_mocker,
    tmp_path,
):
    ts = Teamspace("ts-abc", user="user-abc")

    ts.download_model("user/modelname:v3", download_dir=tmp_path)
    download_model_files_mock.assert_called_with(
        client=mock.ANY,
        teamspace_id="ts-abc002",
        name="user/modelname",
        version="v3",
        download_dir=tmp_path,
        progress_bar=True,
    )
