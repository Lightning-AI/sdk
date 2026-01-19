import os
import subprocess
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


@pytest.mark.parametrize("progress_bar", [True, False])
@mock.patch("requests.put")
@mock.patch("lightning_sdk.api.teamspace_api.tqdm")
@mock.patch("lightning_sdk.api.teamspace_api.Auth")
def test_upload_file(
    auth_mock,
    tqdm_mock,
    requests_put_mock,
    tmpdir,
    progress_bar,
):
    requests_put_mock.return_value.status_code = 200
    tqdm_mock.wrapattr.side_effect = lambda f, *args, **kwargs: f

    auth_instance = auth_mock.return_value
    auth_instance.api_key = "test-api-key"

    teamspace_api = TeamspaceApi()

    # Mock the entire _client object
    teamspace_api._client = mock.Mock()
    teamspace_api._client.auth_service_login.return_value = mock.Mock(token="test-token")
    teamspace_api._client.api_client.configuration.host = "https://api.example.com"

    filepath = os.path.join(tmpdir, "file1")
    subprocess.run(f"truncate -s 40MB {filepath}".split(" "))

    teamspace_api.upload_file("ts-abc", "cluster-abc", filepath, "file1", progress_bar=progress_bar)

    assert requests_put_mock.call_count == 1
    (url,) = requests_put_mock.call_args.args
    params = requests_put_mock.call_args.kwargs["params"]

    assert "ts-abc" in url
    assert "file1" in url
    assert "token" in params

    # Verify tqdm was used only if progress_bar is True
    if progress_bar:
        tqdm_mock.wrapattr.assert_called_once()
    else:
        tqdm_mock.wrapattr.assert_not_called()


def test_download_file(tmpdir, internal_teamspace_api_mocker, internal_studio_api_login):
    file_content = b"test file content"

    mock_s3_response = mock.Mock()
    mock_s3_response.status_code = 200
    mock_s3_response.headers = {"content-length": str(len(file_content))}
    mock_s3_response.iter_content = lambda chunk_size: [file_content]

    def get_side_effect(url, **kwargs):
        return mock_s3_response

    teamspace_api = TeamspaceApi()

    with mock.patch("requests.get", side_effect=get_side_effect):
        teamspace_api = TeamspaceApi()
        filepath = os.path.join(tmpdir, "file1")
        teamspace_api.download_file("file1", filepath, "ts-abc")

        assert os.path.exists(filepath)
        with open(filepath, "rb") as f:
            assert f.read() == file_content


@mock.patch("lightning_sdk.api.teamspace_api.requests")
def test_download_file_error(mock_requests, tmpdir, internal_teamspace_api_mocker, internal_studio_api_login):
    teamspace_api = TeamspaceApi()
    remote_path = "file_dne"
    filepath = os.path.join(tmpdir, "file")

    mock_response = mock.Mock()
    mock_response.status_code = 404
    mock_response.headers = {"content-length": "0"}
    mock_response.iter_content.return_value = []
    mock_requests.get.return_value = mock_response

    with pytest.raises(FileNotFoundError, match=f"The provided path does not exist in the teamspace: {remote_path}"):
        teamspace_api.download_file(remote_path, filepath, "ts-abc")


@mock.patch("lightning_sdk.api.teamspace_api._download_teamspace_files", autospec=True)
def test_download_folder(mock_download, tmpdir):
    teamspace_api = TeamspaceApi()

    teamspace_api.download_folder("folder", tmpdir, "ts-abc", "cluster-abc")
    mock_download.assert_called_once()


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
