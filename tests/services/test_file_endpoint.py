import lightning_sdk.services.file_endpoint as file_endpoint_module
from lightning_sdk.services.file_endpoint import FileEndpoint
from unittest.mock import MagicMock


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
