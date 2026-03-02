import os
import subprocess
import warnings
from pathlib import Path
from unittest import mock

import pytest

from lightning_sdk import Machine
from lightning_sdk.api.teamspace_api import TeamspaceApi
from lightning_sdk.lightning_cloud.openapi import (
    ModelsStoreCreateModelBody,
    ModelsStoreCreateModelVersionBody,
    V1CloudSpace,
    V1ClusterAccelerator,
    V1ListProjectClusterAcceleratorsResponse,
    V1LoginResponse,
    V1Project,
    V1ProjectClusterBinding,
    V1Resources,
    V1Secret,
    V1SecretType,
)


def test_get_teamspace(internal_teamspace_api_mocker):
    teamspace_api = TeamspaceApi()

    project = teamspace_api.get_teamspace("ts-abc", "org-abc")
    assert isinstance(project, V1Project)


def test_get_teamspace_error(internal_teamspace_api_mocker):
    teamspace_api = TeamspaceApi()

    with pytest.raises(ValueError, match="Teamspace xyz does not exist"):
        teamspace_api.get_teamspace("xyz", "org-def")


def test_list_teamspaces(internal_teamspace_api_list_mocker):
    teamspace_api = TeamspaceApi()

    projects = teamspace_api.list_teamspaces("org-abc", name=None)
    assert len(projects) == 2
    assert isinstance(projects[0], V1Project)
    assert isinstance(projects[1], V1Project)

    projects = teamspace_api.list_teamspaces("org-def", name=None)
    assert len(projects) == 1
    assert isinstance(projects[0], V1Project)

    projects = teamspace_api.list_teamspaces("org-abc", name="ts-def")
    assert len(projects) == 1
    assert isinstance(projects[0], V1Project)


def test_list_studios(internal_studio_api_list_mocker):
    teamspace_api = TeamspaceApi()

    studios = teamspace_api.list_studios(cloud_account="cluster_abc", teamspace_id="ts-abc")

    assert len(studios) == 3
    for st in studios:
        assert isinstance(st, V1CloudSpace)


def test_list_clusters(internal_teamspace_api_cluster_list_mocker):
    teamspace_api = TeamspaceApi()

    clusters = teamspace_api.list_cloud_accounts(teamspace_id="ts-abc")

    assert len(clusters) == 2
    for cl in clusters:
        assert isinstance(cl, V1ProjectClusterBinding)


def test_create_agent(internal_teamspace_api_create_agent_mocker):
    teamspace_api = TeamspaceApi()
    agent = teamspace_api.create_agent(
        name="test-sdk",
        teamspace_id="ts-abc",
        base_url="test-sdk",
        api_key="test-sdk",
        model="test-sdk",
        org_id="org-abc",
    )

    assert agent.name == "test-sdk"
    assert agent.project_id == "ts-abc"
    assert agent.model == "test-sdk"


@mock.patch("lightning_sdk.api.teamspace_api._ModelFileUploader")
def test_upload_model_file(uploader_mock):
    teamspace_api = TeamspaceApi()
    teamspace_api.upload_model_file(
        model_id="test-model-id",
        version="latest",
        local_path=Path("path/to/checkpoint.pt"),
        remote_path="modelpath/on/cluster",
        teamspace_id="test-project-id",
        progress_bar=False,
    )
    uploader_mock.assert_called_with(
        client=mock.ANY,
        model_id="test-model-id",
        version="latest",
        file_path="path/to/checkpoint.pt",
        remote_path="modelpath/on/cluster",
        teamspace_id="test-project-id",
        progress_bar=False,
    )
    uploader_mock().assert_called_with()  # .__call__()


def test_try_get_cluster_id():
    # cluster set via env variable
    teamspace_api = TeamspaceApi()
    with mock.patch.dict(os.environ, {"LIGHTNING_CLUSTER_ID": "cluster-via-env"}):
        cluster_id = teamspace_api._determine_cloud_account("teamspace-id")
    assert cluster_id == "cluster-via-env"

    # teamspace has single cluster
    teamspace_api.list_cloud_accounts = mock.Mock(return_value=[mock.Mock(cluster_id="test-cluster")])
    teamspace_api.get_default_cloud_account = mock.Mock(return_value="test-cluster")
    with mock.patch.dict(os.environ, {"LIGHTNING_CLUSTER_ID": ""}):
        cluster_id = teamspace_api._determine_cloud_account("teamspace-id")
    assert cluster_id == "test-cluster"

    # disabled cluster default
    teamspace_api.get_default_cloud_account = mock.Mock(return_value="")

    # ambiguous, can't determine which cluster to use
    teamspace_api.list_cloud_accounts = mock.Mock(
        return_value=[
            mock.Mock(cluster_id="test-cluster-1"),
            mock.Mock(cluster_id="test-cluster-2"),
        ]
    )
    with mock.patch.dict(os.environ, {"LIGHTNING_CLUSTER_ID": ""}), pytest.raises(
        RuntimeError, match="Could not determine the current cloud account"
    ):
        _ = teamspace_api._determine_cloud_account("teamspace-id")


def test_create_delete_model():
    teamspace_api = TeamspaceApi()
    # create a content reused in following cases
    model_body = {"name": "model-name", "metadata": {}, "private": True, "cluster_id": "cluster-abc"}
    # mock the models_store_list_models and models_store_create_model for empty state
    teamspace_api._models_api = mock.MagicMock(
        models_store_list_models=mock.MagicMock(return_value=mock.MagicMock(models=[])),
        models_store_create_model=mock.MagicMock(return_value=mock.MagicMock(model_id="model-id")),
    )
    teamspace_api.create_model(
        teamspace_id="ts-abc", name="model-name", version="vvv", metadata={}, private=True, cloud_account="cluster-abc"
    )
    # validate the calls
    teamspace_api._models_api.models_store_list_models.assert_called_with(project_id="ts-abc", name="model-name")
    teamspace_api._models_api.models_store_create_model.assert_called_with(
        body=ModelsStoreCreateModelBody(**model_body), project_id="ts-abc"
    )

    # mock the models_store_list_models and models_store_create_model for non-empty state
    teamspace_api._models_api = mock.MagicMock(
        models_store_list_models=mock.MagicMock(return_value=mock.MagicMock(models=[mock.MagicMock(id="model-id")])),
        models_store_delete_model=mock.MagicMock(),
    )
    # delete the model calls
    teamspace_api.delete_model(name="model-name", version="", teamspace_id="ts-abc")
    teamspace_api._models_api.models_store_list_models.assert_called_with(project_id="ts-abc", name="model-name")
    teamspace_api._models_api.models_store_delete_model.assert_called_with(project_id="ts-abc", model_id="model-id")


def test_create_delete_model_version():
    teamspace_api = TeamspaceApi()
    # mock the models_store_list_models and models_store_create_model_version for existing model
    teamspace_api._models_api = mock.MagicMock(
        models_store_list_models=mock.MagicMock(return_value=mock.MagicMock(models=[mock.MagicMock(id="model-id")])),
        models_store_create_model_version=mock.MagicMock(
            return_value=mock.MagicMock(model_id="model-id", version="v1")
        ),
    )
    version = teamspace_api.create_model(
        teamspace_id="ts-abc",
        name="model-name",
        version="vVv",
        metadata={},
        private=True,
        cloud_account="cluster-abc",
    )
    teamspace_api._models_api.models_store_list_models.assert_called_with(project_id="ts-abc", name="model-name")
    teamspace_api._models_api.models_store_create_model_version.assert_called_with(
        project_id="ts-abc",
        body=ModelsStoreCreateModelVersionBody(cluster_id="cluster-abc", version="vVv"),
        model_id="model-id",
    )

    teamspace_api._models_api = mock.MagicMock(
        models_store_list_models=mock.MagicMock(
            return_value=mock.MagicMock(models=[mock.MagicMock(id="model-id", default_version="v1")])
        ),
    )
    teamspace_api.delete_model(name="model-name", version="default", teamspace_id="ts-abc")
    teamspace_api._models_api.models_store_delete_model_version.assert_called_with(
        project_id="ts-abc", model_id="model-id", version=version.version
    )
    teamspace_api.delete_model(name="model-name", version=version.version, teamspace_id="ts-abc")
    teamspace_api._models_api.models_store_delete_model_version.assert_called_with(
        project_id="ts-abc", model_id="model-id", version=version.version
    )


@mock.patch("lightning_sdk.api.cloud_account_api.CloudAccountApi")
def test_list_machines(mock_cloud_account_api_class):
    mock_cloud_account_api = mock.Mock()
    mock_cloud_account_api_class.return_value = mock_cloud_account_api

    mock_accelerators = V1ListProjectClusterAcceleratorsResponse(
        accelerator=[
            V1ClusterAccelerator(
                instance_id="instance-id",
                slug="t4-x-2",
                slug_multi_cloud="lit-t4-2",
                resources=V1Resources(cpu=4, gpu=2),
            )
        ]
    )
    mock_cloud_account_api.list_cloud_account_accelerators.return_value = mock_accelerators

    teamspace_api = TeamspaceApi()
    result = teamspace_api.list_machines("teamspace-id", ["cloud-account"])

    assert len(result) == 1
    assert result[0].instance_id == "instance-id"

    mock_cloud_account_api.list_cloud_account_accelerators.assert_called_once_with(
        teamspace_id="teamspace-id", cloud_account_id="cloud-account", org_id=None
    )


@mock.patch("lightning_sdk.api.cloud_account_api.CloudAccountApi")
def test_list_machines_with_specific_machine(mock_cloud_account_api_class):
    mock_cloud_account_api = mock.Mock()
    mock_cloud_account_api_class.return_value = mock_cloud_account_api

    mock_accelerators = V1ListProjectClusterAcceleratorsResponse(
        accelerator=[
            V1ClusterAccelerator(
                instance_id="h100-x-8",
                slug="h100-x-8",
                slug_multi_cloud="lit-h100-8",
                resources=V1Resources(cpu=0, gpu=8),
                family="H100",
            ),
            V1ClusterAccelerator(
                instance_id="a100-x-8",
                slug="a100-x-8",
                slug_multi_cloud="lit-a100-8",
                resources=V1Resources(cpu=0, gpu=8),
                family="A100",
            ),
        ]
    )

    mock_cloud_account_api.list_cloud_account_accelerators.return_value = mock_accelerators

    teamspace_api = TeamspaceApi()
    teamspace_api.id = "ts-abc"

    machine = Machine(
        name="A100",
        family="A100",
        accelerator_count=8,
        slug="a100-x-8",
    )

    result = teamspace_api.list_machines(
        teamspace_id="ts-abc",
        machine=machine,
        cloud_accounts=["cluster-abc", "cluster-def"],
        org_id="org-123",
    )

    assert len(result) == 2
    assert all(r.resources.gpu == 8 for r in result)

    assert mock_cloud_account_api.list_cloud_account_accelerators.call_count == 2
    mock_cloud_account_api.list_cloud_account_accelerators.assert_any_call(
        teamspace_id="ts-abc",
        cloud_account_id="cluster-abc",
        org_id="org-123",
    )
    mock_cloud_account_api.list_cloud_account_accelerators.assert_any_call(
        teamspace_id="ts-abc",
        cloud_account_id="cluster-def",
        org_id="org-123",
    )


def test_get_model_errors(internal_teamspace_api_mocker):
    teamspace_api = TeamspaceApi()

    with pytest.raises(ValueError, match="Either `model_id` or `model_name` must be provided."):
        teamspace_api.get_model("xyz")

    # mock the response for empty state
    teamspace_api._models_api = mock.MagicMock(
        models_store_list_models=mock.MagicMock(return_value=mock.MagicMock(models=[])),
    )
    with pytest.raises(ValueError, match="Model 'model-name' does not exist."):
        teamspace_api.get_model("xyz", model_name="model-name")

    # mock the response for too many models
    teamspace_api._models_api = mock.MagicMock(
        models_store_list_models=mock.MagicMock(return_value=mock.MagicMock(models=[mock.Mock(), mock.Mock()])),
    )
    with pytest.raises(RuntimeError, match="Model name 'model-name' is not a unique with this teamspace."):
        teamspace_api.get_model("xyz", model_name="model-name")


@mock.patch("requests.get", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.auth_service_api.AuthServiceApi.auth_service_login", autospec=True
)
def test_get_tree(mock_login, mock_requests_get):
    """Test get_tree retrieves directory structure from teamspace drive."""
    mock_login.return_value = V1LoginResponse(token="test-token")

    mock_response = mock.MagicMock()
    mock_response.json.return_value = {
        "tree": [
            {"path": "file1.txt", "type": "blob", "size": 1234},
            {"path": "folder1", "type": "tree"},
            {"path": "file2.py", "type": "blob", "size": 5678},
        ],
        "truncated": False,
    }
    mock_requests_get.return_value = mock_response

    teamspace_api = TeamspaceApi()

    result = teamspace_api.get_tree("ts-abc", "my-folder/")

    assert result == {
        "tree": [
            {"path": "file1.txt", "type": "blob", "size": 1234},
            {"path": "folder1", "type": "tree"},
            {"path": "file2.py", "type": "blob", "size": 5678},
        ],
        "truncated": False,
    }

    mock_requests_get.assert_called_once()
    call_args = mock_requests_get.call_args

    assert "/v1/projects/ts-abc/artifacts/trees/my-folder/" in call_args[0][0]
    assert call_args[1]["params"] == {"token": "test-token"}
    mock_login.assert_called_once()


@pytest.mark.parametrize(
    ("path", "tree_response", "expected_result"),
    [
        (
            "",
            None,
            {"exists": True, "type": "directory", "size": None},
        ),
        # file exists
        (
            "test.txt",
            {"tree": [{"path": "test.txt", "type": "blob", "size": 1024}]},
            {"exists": True, "type": "file", "size": 1024},
        ),
        # directory exists
        (
            "test-dir",
            {"tree": [{"path": "test-dir", "type": "tree"}]},
            {"exists": True, "type": "directory", "size": None},
        ),
        # Test case 3: File does not exist (empty tree)
        (
            "nonexistent.txt",
            {"tree": []},
            {"exists": False, "type": None, "size": None},
        ),
        # nested file
        (
            "path/to/data.csv",
            {"tree": [{"path": "data.csv", "type": "blob", "size": 2048}]},
            {"exists": True, "type": "file", "size": 2048},
        ),
        # nested directory
        (
            "path/to/subfolder",
            {"tree": [{"path": "subfolder", "type": "tree"}]},
            {"exists": True, "type": "directory", "size": None},
        ),
    ],
)
@mock.patch("requests.get", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.auth_service_api.AuthServiceApi.auth_service_login",
    autospec=True,
)
def test_get_path_info(mock_login, mock_requests_get, path, tree_response, expected_result):
    from lightning_sdk.lightning_cloud.openapi import V1LoginResponse

    mock_login.return_value = V1LoginResponse(token="test-token")

    mock_response = mock.MagicMock()
    mock_response.json.return_value = tree_response
    mock_requests_get.return_value = mock_response

    teamspace_api = TeamspaceApi()

    if not expected_result["exists"]:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = teamspace_api.get_path_info("ts-abc", path)

            # Check warning was raised
            assert len(w) == 1
            assert "may be empty" in str(w[0].message)
    else:
        result = teamspace_api.get_path_info("ts-abc", path)

    assert result == expected_result

    if path.strip("/") == "":
        mock_requests_get.assert_not_called()
    else:
        if "/" in path:
            expected_parent = path.rsplit("/", 1)[0]
            assert expected_parent in mock_requests_get.call_args[0][0]
        else:
            # root level should include /trees/
            call_url = mock_requests_get.call_args[0][0]
            assert "/trees/" in call_url


@pytest.mark.parametrize(
    ("path", "mock_response", "expected_files"),
    [
        # nested directories with multiple levels
        (
            "my-folder",
            {
                "tree": [
                    {"path": "file1.txt", "type": "blob"},
                    {"path": "folder1/nested.txt", "type": "blob", "size": 999},
                    {"path": "folder1/subfolder/deep.txt", "type": "blob", "size": 111},
                    {"path": "file2.py", "type": "blob"},
                ],
                "truncated": False,
            },
            [
                {"path": "file1.txt", "type": "blob"},
                {"path": "folder1/nested.txt", "type": "blob", "size": 999},
                {"path": "folder1/subfolder/deep.txt", "type": "blob", "size": 111},
                {"path": "file2.py", "type": "blob"},
            ],
        ),
        # empty directory
        (
            "empty-folder",
            {
                "tree": [],
                "truncated": False,
            },
            [],
        ),
        # root path (empty string)
        (
            "",
            {
                "tree": [
                    {"path": "root-file.txt", "type": "blob", "size": 100},
                ],
                "truncated": False,
            },
            [
                {"path": "root-file.txt", "type": "blob", "size": 100},
            ],
        ),
        # path with leading/trailing slashes
        (
            "/my-folder/",
            {
                "tree": [
                    {"path": "file.txt", "type": "blob"},
                ],
                "truncated": False,
            },
            [
                {"path": "file.txt", "type": "blob"},
            ],
        ),
    ],
)
@mock.patch("requests.get", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.auth_service_api.AuthServiceApi.auth_service_login", autospec=True
)
def test_list_files(
    mock_login,
    mock_requests_get,
    path,
    mock_response,
    expected_files,
):
    """Test that list_files correctly calls get_tree with recursive=true."""
    mock_login.return_value = V1LoginResponse(token="test-token")

    teamspace_api = TeamspaceApi()
    mock_response_obj = mock.MagicMock()
    mock_response_obj.json.return_value = mock_response
    mock_requests_get.return_value = mock_response_obj

    result = teamspace_api.list_files(
        teamspace_id="ts-abc",
        path=path,
    )

    assert mock_requests_get.call_count == 1
    call_args = mock_requests_get.call_args

    # get_uploads_tree
    host = teamspace_api._client.api_client.configuration.host
    expected_url = f"{host}/v1/projects/ts-abc/artifacts/trees/{path.strip('/')}"
    assert call_args[0][0] == expected_url

    # recursive
    assert call_args[1]["params"]["recursive"] == "true"

    assert result == expected_files


@pytest.mark.parametrize("progress_bar", [True, False])
@pytest.mark.parametrize("file_size_mb", [4, 200])  # 4MB for single-part, 100MB for multipart
@mock.patch("lightning_sdk.api.teamspace_api._FileUploader")
@mock.patch("requests.post")
@mock.patch("requests.put")
@mock.patch("lightning_sdk.api.utils.tqdm")
@mock.patch("lightning_sdk.api.teamspace_api.Auth")
def test_upload_file(
    auth_mock,
    tqdm_mock,
    requests_put_mock,
    requests_post_mock,
    file_uploader_mock,
    tmpdir,
    progress_bar,
    file_size_mb,
):
    requests_put_mock.return_value.status_code = 200
    requests_post_mock.return_value.status_code = 200
    tqdm_mock.wrapattr.side_effect = lambda f, *args, **kwargs: f
    auth_instance = auth_mock.return_value
    auth_instance.api_key = "test-api-key"
    teamspace_api = TeamspaceApi()

    teamspace_api._client = mock.Mock()
    teamspace_api._client.auth_service_login.return_value = mock.Mock(token="test-token")
    teamspace_api._client.api_client.configuration.host = "https://api.example.com"

    filepath = os.path.join(tmpdir, "file1")
    subprocess.run(f"truncate -s {file_size_mb}MB {filepath}".split(" "))

    teamspace_api.upload_file("ts-abc", "cluster-abc", filepath, "file1", progress_bar=progress_bar)

    if file_size_mb <= 100:
        # Single-part upload should be used
        assert requests_put_mock.call_count == 1
        (url,) = requests_put_mock.call_args.args
        params = requests_put_mock.call_args.kwargs["params"]
        assert "ts-abc" in url
        assert "file1" in url
        assert "token" in params

        # FileUploader (multipart) should not be called
        file_uploader_mock.assert_not_called()

        if progress_bar:
            tqdm_mock.wrapattr.assert_called_once()
        else:
            tqdm_mock.wrapattr.assert_not_called()
    else:
        # Multipart upload should be used
        file_uploader_mock.assert_called_once()
        call_kwargs = file_uploader_mock.call_args.kwargs
        assert call_kwargs["teamspace_id"] == "ts-abc"
        assert call_kwargs["cloud_account"] == "cluster-abc"
        assert call_kwargs["file_path"] == filepath
        assert call_kwargs["progress_bar"] == progress_bar

        # Single-part upload should not be called
        assert requests_put_mock.call_count == 0


@pytest.mark.parametrize("progress_bar", [True, False])
@mock.patch("requests.post")
@mock.patch("requests.put")
@mock.patch("lightning_sdk.api.teamspace_api.tqdm")
@mock.patch("lightning_sdk.api.teamspace_api.Auth")
def test_upload_file_with_headers(
    auth_mock,
    tqdm_mock,
    requests_put_mock,
    requests_post_mock,
    tmpdir,
    progress_bar,
):
    """Test that custom headers are passed to requests.put when uploading files."""
    requests_put_mock.return_value.status_code = 200
    requests_post_mock.return_value.status_code = 200
    tqdm_mock.wrapattr.side_effect = lambda f, *args, **kwargs: f

    auth_instance = auth_mock.return_value
    auth_instance.api_key = "test-api-key"

    teamspace_api = TeamspaceApi()

    # Mock the entire _client object
    teamspace_api._client = mock.Mock()
    teamspace_api._client.auth_service_login.return_value = mock.Mock(token="test-token")
    teamspace_api._client.api_client.configuration.host = "https://api.example.com"

    filepath = os.path.join(tmpdir, "file1")
    subprocess.run(f"truncate -s 1MB {filepath}".split(" "))

    custom_headers = {"Content-Type": "image/png"}
    teamspace_api.upload_file(
        "ts-abc", "cluster-abc", filepath, "file1", progress_bar=progress_bar, headers=custom_headers
    )

    assert requests_put_mock.call_count == 1
    headers = requests_put_mock.call_args.kwargs["headers"]

    assert headers == custom_headers
    assert headers["Content-Type"] == "image/png"


@mock.patch("requests.post")
@mock.patch("requests.put")
@mock.patch("lightning_sdk.api.teamspace_api.Auth")
def test_upload_file_without_headers(
    auth_mock,
    requests_put_mock,
    requests_post_mock,
    tmpdir,
):
    """Test that headers is None by default when not provided."""
    requests_put_mock.return_value.status_code = 200
    requests_post_mock.return_value.status_code = 200

    auth_instance = auth_mock.return_value
    auth_instance.api_key = "test-api-key"

    teamspace_api = TeamspaceApi()

    teamspace_api._client = mock.Mock()
    teamspace_api._client.auth_service_login.return_value = mock.Mock(token="test-token")
    teamspace_api._client.api_client.configuration.host = "https://api.example.com"

    filepath = os.path.join(tmpdir, "file1")
    subprocess.run(f"truncate -s 1MB {filepath}".split(" "))

    teamspace_api.upload_file("ts-abc", "cluster-abc", filepath, "file1", progress_bar=False)

    assert requests_put_mock.call_count == 1
    headers = requests_put_mock.call_args.kwargs["headers"]

    assert headers is None


@mock.patch("requests.get", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.auth_service_api.AuthServiceApi.auth_service_login", autospec=True
)
def test_download_file(mock_login, mock_requests_get, tmpdir):
    mock_login.return_value = V1LoginResponse(token="token")

    teamspace_api = TeamspaceApi()

    filepath = os.path.join(tmpdir, "file1")
    teamspace_api.download_file("file1", filepath, "ts-abc", "cluster-abc")


@mock.patch("lightning_sdk.api.teamspace_api.concurrent.futures.wait")
@mock.patch("lightning_sdk.api.teamspace_api.tqdm")
@mock.patch("lightning_sdk.api.teamspace_api.ThreadPoolExecutor")
@mock.patch("lightning_sdk.api.teamspace_api._authenticate_and_get_token")
def test_download_folder(authenticate_mock, mock_executor, mock_tqdm, mock_wait, tmpdir):
    authenticate_mock.return_value = "test-token-123"

    teamspace_api = TeamspaceApi()

    teamspace_api.list_files = mock.Mock(
        return_value=[
            {"path": "file1.txt", "size": 1000},
            {"path": "file2.txt", "size": 2000},
        ]
    )

    teamspace_api._download_single_file = mock.Mock()

    mock_future = mock.Mock()
    mock_executor.return_value.__enter__.return_value.submit.return_value = mock_future
    mock_wait.return_value = None

    filepath = os.path.join(tmpdir, "download_folder")
    teamspace_api.download_folder("file1", filepath, "ts-abc", "cluster-abc")

    teamspace_api.list_files.assert_called_once_with("ts-abc", "file1")

    mock_executor.assert_called_once()

    mock_tqdm.assert_called_once()
    assert mock_tqdm.call_args.kwargs["desc"] == "Downloading files"
    assert mock_tqdm.call_args.kwargs["total"] == 3000  # 1000 + 2000


def test_get_secrets():
    teamspace_api = TeamspaceApi()

    mock_secrets = [
        V1Secret(id="secret-1", name="API_KEY", type=V1SecretType.UNSPECIFIED),
        V1Secret(id="secret-2", name="DATABASE_URL", type=V1SecretType.UNSPECIFIED),
    ]

    with mock.patch.object(teamspace_api, "_get_secrets", return_value=mock_secrets):
        secrets = teamspace_api.get_secrets("ts-abc")

    assert len(secrets) == 2
    assert secrets["API_KEY"] == "***REDACTED***"
    assert secrets["DATABASE_URL"] == "***REDACTED***"


def test_set_secret_create_new():
    teamspace_api = TeamspaceApi()

    existing_secrets = [
        V1Secret(id="secret-1", name="API_KEY"),
    ]

    with mock.patch.object(teamspace_api, "_get_secrets", return_value=existing_secrets), mock.patch.object(
        teamspace_api, "_create_secret"
    ) as mock_create:
        teamspace_api.set_secret("ts-abc", "NEW_SECRET", "secret_value")

        mock_create.assert_called_once_with("ts-abc", "NEW_SECRET", "secret_value")


def test_set_secret_update_existing():
    teamspace_api = TeamspaceApi()

    existing_secrets = [
        V1Secret(id="secret-1", name="API_KEY"),
        V1Secret(id="secret-2", name="DATABASE_URL"),
    ]

    with mock.patch.object(teamspace_api, "_get_secrets", return_value=existing_secrets), mock.patch.object(
        teamspace_api, "_update_secret"
    ) as mock_update:
        teamspace_api.set_secret("ts-abc", "API_KEY", "new_secret_value")

        mock_update.assert_called_once_with("ts-abc", "secret-1", "new_secret_value")


@mock.patch("lightning_sdk.api.teamspace_api.LightningClient")
def test_get_secrets_api_call(mock_client):
    mock_client().secret_service_list_secrets.return_value.secrets = [
        V1Secret(id="secret-1", name="API_KEY"),
    ]

    teamspace_api = TeamspaceApi()
    result = teamspace_api._get_secrets("ts-abc")

    mock_client().secret_service_list_secrets.assert_called_once_with(project_id="ts-abc")
    assert len(result) == 1
    assert result[0].name == "API_KEY"


@mock.patch("lightning_sdk.api.teamspace_api.LightningClient")
def test_create_secret_api_call(mock_client):
    teamspace_api = TeamspaceApi()

    teamspace_api._create_secret("ts-abc", "NEW_SECRET", "secret_value")

    mock_client().secret_service_create_secret.assert_called_once()
    call_args = mock_client().secret_service_create_secret.call_args
    assert call_args[1]["project_id"] == "ts-abc"
    assert call_args[1]["body"].name == "NEW_SECRET"
    assert call_args[1]["body"].value == "secret_value"
    assert call_args[1]["body"].type == V1SecretType.UNSPECIFIED


@mock.patch("lightning_sdk.api.teamspace_api.LightningClient")
def test_update_secret_api_call(mock_client):
    teamspace_api = TeamspaceApi()

    teamspace_api._update_secret("ts-abc", "secret-1", "new_value")

    mock_client().secret_service_update_secret.assert_called_once()
    call_args = mock_client().secret_service_update_secret.call_args
    assert call_args[1]["project_id"] == "ts-abc"
    assert call_args[1]["id"] == "secret-1"
    assert call_args[1]["body"].value == "new_value"


@pytest.mark.parametrize(
    ("secret_name", "expected"),
    [
        ("VALID_SECRET", True),
        ("valid_secret", True),
        ("_VALID_SECRET", True),
        ("_valid_secret", True),
        ("SECRET_123", True),
        ("secret123", True),
        ("a", True),
        ("_", True),
        ("A_B_C_123", True),
        ("123_INVALID", False),  # starts with number
        ("INVALID-SECRET", False),  # contains hyphen
        ("INVALID SECRET", False),  # contains space
        ("INVALID.SECRET", False),  # contains dot
        ("", False),  # empty string
        ("INVALID@SECRET", False),  # contains special character
        ("INVALID#SECRET", False),  # contains hash
        ("INVALID$SECRET", False),  # contains dollar sign
    ],
)
def test_verify_secret_name(secret_name, expected):
    teamspace_api = TeamspaceApi()
    result = teamspace_api.verify_secret_name(secret_name)
    assert result == expected
