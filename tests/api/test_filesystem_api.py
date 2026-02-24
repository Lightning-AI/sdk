import os
from unittest import mock

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
