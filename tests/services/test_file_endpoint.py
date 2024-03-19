import os
import lightning_sdk.services.file_endpoint as file_endpoint_module
import lightning_sdk.services.uploader as uploader_module
from lightning_sdk.services.file_endpoint import FileEndpoint, Client
from unittest.mock import MagicMock
from lightning_sdk.lightning_cloud.openapi import (
    V1FileEndpoint,
    V1CommandArgument,
    CommandArgumentCommandArgumentType,
    V1ServiceExecution,
    V1UploadServiceExecutionArtifactResponse,
    V1PresignedUrl,
    V1GetServiceExecutionStatusResponse,
    V1ServiceArtifact,
    ServiceArtifactArtifactKind,
    V1DownloadServiceExecutionArtifactResponse,
    V1ProjectArtifact,
)
import pytest


def test_file_endpoint(monkeypatch):
    requests_mock = MagicMock()

    responses = [
        {"run_id": "run_id", "files_to_upload": [{"name": "name", "upload_id": "upload_id"}]},
        {"run_id": "run_id", "stage": "running"},
        {"run_id": "run_id", "stage": "running"},
        {"run_id": "run_id", "stage": "completed"},
    ]

    def fn(url, *args, **kwargs):
        response = MagicMock()
        response.status_code = 200
        json = responses.pop(0)
        response.json.return_value = json
        return response

    requests_mock.post = fn

    monkeypatch.setattr(file_endpoint_module, "requests", requests_mock)
    monkeypatch.setattr(file_endpoint_module, "sleep", MagicMock())
    client = FileEndpoint(url="url")
    client.run(files={"name": __file__})


def test_file_endpoint_client(tmpdir, monkeypatch):
    lightning_client_mock = MagicMock()
    monkeypatch.setattr(file_endpoint_module, "LightningClient", MagicMock(return_value=lightning_client_mock))
    monkeypatch.setattr(file_endpoint_module, "Auth", MagicMock())
    monkeypatch.setattr(file_endpoint_module, "_get_project", MagicMock())

    requests_mock = MagicMock()

    monkeypatch.setattr(uploader_module, "requests", requests_mock)

    lightning_client_mock.endpoint_service_get_file_endpoint.return_value = V1FileEndpoint(
        arguments=[
            V1CommandArgument(name="image_size", type=CommandArgumentCommandArgumentType.TEXT),
            V1CommandArgument(name="image_path", type=CommandArgumentCommandArgumentType.FILE),
        ]
    )

    lightning_client_mock.endpoint_service_get_file_endpoint.return_value = V1FileEndpoint(
        arguments=[
            V1CommandArgument(name="image_size", type=CommandArgumentCommandArgumentType.TEXT),
            V1CommandArgument(name="image_path", type=CommandArgumentCommandArgumentType.FILE),
        ]
    )

    lightning_client_mock.endpoint_service_create_service_execution.return_value = V1ServiceExecution(
        id="service_execution_id",
        arguments=[
            V1CommandArgument(name="image_size", type=CommandArgumentCommandArgumentType.TEXT, id="upload_id_1"),
            V1CommandArgument(
                name="image_path",
                type=CommandArgumentCommandArgumentType.FILE,
                id="upload_id_2",
            ),
        ],
    )

    lightning_client_mock.endpoint_service_upload_service_execution_artifact.return_value = (
        V1UploadServiceExecutionArtifactResponse(upload_id=None, urls=[V1PresignedUrl(url="url")])
    )

    lightning_client_mock.endpoint_service_get_service_execution_status.return_value = (
        V1GetServiceExecutionStatusResponse(
            phase="COMPLETED",
            artifacts=[
                V1ServiceArtifact(kind=ServiceArtifactArtifactKind.JSON, value={}),
                V1ServiceArtifact(kind=ServiceArtifactArtifactKind.FILE, value="a.txt"),
                V1ServiceArtifact(kind=ServiceArtifactArtifactKind.FOLDER, value="a"),
            ],
        )
    )

    lightning_client_mock.endpoint_service_download_service_execution_artifact.return_value = V1DownloadServiceExecutionArtifactResponse(
        next_page_token="",
        artifacts=[
            V1ProjectArtifact(
                filename="a.txt",
                url="https://raw.githubusercontent.com/Lightning-AI/pytorch-lightning/093fac191dd8cc815df7123932fc4493917cd9bd/docs/source-pytorch/conf.py",
            )
        ],
    )

    client = Client(id="file_endpoint_id")

    with pytest.raises(ValueError, match="This endpoint expects a value for the argument `image_size`."):
        client.run()

    with pytest.raises(ValueError, match="This endpoint expects a file for the argument `image_path`."):
        client.run(image_size=256)

    client.run(image_size=256, image_path=__file__, artifacts_dir=tmpdir)

    requests_mock.put.assert_called()

    assert os.path.exists(os.path.join(tmpdir, "a.txt"))
    assert os.path.exists(os.path.join(tmpdir, "a", "a.txt"))
