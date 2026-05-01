from unittest.mock import ANY, MagicMock

import lightning_sdk.services.file_endpoint as file_endpoint_module
from lightning_sdk.services import LLMFinetune


def test_llm_finetune(monkeypatch):
    requests_mock = MagicMock()

    arguments = [
        (
            "https://fid-csid.cloudspaces.lightning.ai",
            {
                "teamspace_id": "teamspace_id",
                "cluster_id": "cluster_id",
                "input": ANY,
            },
        ),
        ("https://fid-csid.cloudspaces.lightning.ai?run_id=run_id", None),
        ("https://fid-csid.cloudspaces.lightning.ai?run_id=run_id", None),
        ("https://fid-csid.cloudspaces.lightning.ai?run_id=run_id", None),
    ]

    responses = [
        {"run_id": "run_id", "stage": "running"},
        {"run_id": "run_id", "stage": "running"},
        {"run_id": "run_id", "stage": "completed"},
    ]

    def fn(url, json=None, files=None, headers=None):
        expected_url, expected_json = arguments.pop(0)
        assert expected_url == url
        assert expected_json == json

        response = MagicMock()
        response.status_code = 200
        json = responses.pop(0)
        response.json.return_value = json
        response.headers = {file_endpoint_module._LIGHTNING_SERVICE_EXECUTION_ID_HEADER: "service_id"}
        return response

    requests_mock.post = fn

    monkeypatch.setattr(file_endpoint_module, "requests", requests_mock)
    monkeypatch.setattr(file_endpoint_module, "sleep", MagicMock())
    lightning_client_mock = MagicMock()
    file_endpoint_mock = MagicMock()
    file_endpoint_mock.id = "fid"
    file_endpoint_mock.cloudspace_id = "csid"
    lightning_client_mock.endpoint_service_get_file_endpoint_by_name.return_value = file_endpoint_mock
    lightning_client_mock.endpoint_service_get_file_endpoint_by_name.return_value = file_endpoint_mock
    project_mock = MagicMock()
    project_mock.project_id = "teamspace_id"
    monkeypatch.setattr(file_endpoint_module, "_get_project", MagicMock(return_value=project_mock))
    cluster_mock = MagicMock()
    cluster_mock.cluster_id = "cluster_id"
    monkeypatch.setattr(file_endpoint_module, "_get_cluster", MagicMock(return_value=cluster_mock))

    monkeypatch.setattr(file_endpoint_module, "LightningClient", MagicMock(return_value=lightning_client_mock))
    auth_mock = MagicMock()
    auth_mock.api_key = "api_key"
    monkeypatch.setattr(file_endpoint_module, "Auth", MagicMock(return_value=auth_mock))

    client = LLMFinetune(teamspace="teamspace")
    client.run(data_path=__file__)
