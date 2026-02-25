import os
from unittest import mock

import pytest

from lightning_sdk.api.filesystem_api import FilesystemApi
from lightning_sdk.lightning_cloud.openapi import V1LoginResponse


@mock.patch("requests.get", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.auth_service_api.AuthServiceApi.auth_service_login", autospec=True
)
def test_download_file(mock_login, mock_requests_get, tmpdir):
    mock_login.return_value = V1LoginResponse(token="token")

    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-length": "0"}
    mock_response.iter_content.return_value = iter([])
    mock_requests_get.return_value = mock_response

    filesystem_api = FilesystemApi()

    filepath = os.path.join(tmpdir, "file1")
    filesystem_api.download_file("file1", filepath, "ts-abc")


@mock.patch("requests.get", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.auth_service_api.AuthServiceApi.auth_service_login", autospec=True
)
def test_list_files_returns_tree(mock_login, mock_requests_get):
    mock_login.return_value = V1LoginResponse(token="token")
    fake_files = [{"name": "test1.txt"}, {"name": "test2.txt"}]
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"tree": fake_files}
    mock_requests_get.return_value = mock_response

    filesystem_api = FilesystemApi()
    result = filesystem_api.list_files(teamspace_id="ts-abc", path="path/to/files")

    assert result == fake_files


@mock.patch("requests.get", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.auth_service_api.AuthServiceApi.auth_service_login", autospec=True
)
def test_list_files_returns_empty_when_tree_missing(mock_login, mock_requests_get):
    mock_login.return_value = V1LoginResponse(token="token")
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_requests_get.return_value = mock_response

    filesystem_api = FilesystemApi()
    result = filesystem_api.list_files(teamspace_id="ts-abc", path="path/to/files")

    assert result == []


@mock.patch("requests.get", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.auth_service_api.AuthServiceApi.auth_service_login", autospec=True
)
def test_list_files_passes_correct_url_and_params(mock_login, mock_requests_get):
    mock_login.return_value = V1LoginResponse(token="token")
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"tree": []}
    mock_requests_get.return_value = mock_response

    filesystem_api = FilesystemApi()
    filesystem_api.list_files(teamspace_id="ts-abc", path="path/to/files/", recursive=True)

    mock_requests_get.assert_called_once()
    url = mock_requests_get.call_args[0][0]
    params = mock_requests_get.call_args[1]["params"]

    assert "ts-abc" in url
    assert "path/to/files" in url
    assert params["recursive"] == "true"
    assert params["token"] == "token"


@mock.patch("requests.get", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.auth_service_api.AuthServiceApi.auth_service_login", autospec=True
)
def test_list_files_non_recursive_by_default(mock_login, mock_requests_get):
    mock_login.return_value = V1LoginResponse(token="token")
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"tree": []}
    mock_requests_get.return_value = mock_response

    filesystem_api = FilesystemApi()
    filesystem_api.list_files(teamspace_id="ts-abc", path="path/to/files")

    params = mock_requests_get.call_args[1]["params"]
    assert params["recursive"] == "false"


@mock.patch("requests.get", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.auth_service_api.AuthServiceApi.auth_service_login", autospec=True
)
def test_list_files_raises_on_non_200(mock_login, mock_requests_get):
    mock_login.return_value = V1LoginResponse(token="token")
    mock_response = mock.MagicMock()
    mock_response.status_code = 404
    mock_requests_get.return_value = mock_response

    filesystem_api = FilesystemApi()
    with pytest.raises(RuntimeError, match="Failed to list files: 404"):
        filesystem_api.list_files(teamspace_id="ts-abc", path="path/to/files")
