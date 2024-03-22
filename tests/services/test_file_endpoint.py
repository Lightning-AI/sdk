import lightning_sdk.services.file_endpoint as file_endpoint_module
from lightning_sdk.services.file_endpoint import Client
from unittest.mock import MagicMock
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

    lightning_client_mock = MagicMock()
    monkeypatch.setattr(file_endpoint_module, "_get_project", MagicMock())
    monkeypatch.setattr(file_endpoint_module, "_get_cluster", MagicMock())

    monkeypatch.setattr(file_endpoint_module, "LightningClient", MagicMock(return_value=lightning_client_mock))
    monkeypatch.setattr(file_endpoint_module, "Auth", MagicMock())
    client = Client(name="name", teamspace="teamspace")
    client.run(name=__file__)
