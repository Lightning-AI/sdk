import lightning_sdk.services.file_endpoint as file_endpoint_module
from lightning_sdk.services import LLMFinetune
from unittest.mock import MagicMock


def test_llm_finetune(monkeypatch):
    requests_mock = MagicMock()

    arguments = [
        (
            "https://fid-csid.cloudspaces.lightning.ai:443",
            {
                "api_key": "api_key",
                "teamspace": "teamspace",
                "cluster_id": "cluster_id",
                "arguments": {
                    "model": "tiny-llama",
                    "mode": "lora",
                    "epochs": "3",
                    "learning_rate": "0.0002",
                    "micro_batch_size": "2",
                    "global_batch_size": "8",
                },
            },
        ),
        ("https://fid-csid.cloudspaces.lightning.ai:443?run_id=run_id", {"api_key": "api_key"}),
        ("https://fid-csid.cloudspaces.lightning.ai:443?run_id=run_id", {"api_key": "api_key"}),
        ("https://fid-csid.cloudspaces.lightning.ai:443?run_id=run_id", {"api_key": "api_key"}),
    ]

    responses = [
        {"run_id": "run_id", "files_to_upload": [{"name": "data_path", "upload_id": "upload_id"}]},
        {"run_id": "run_id", "stage": "running"},
        {"run_id": "run_id", "stage": "running"},
        {"run_id": "run_id", "stage": "completed"},
    ]

    def fn(url, json=None, files=None, headers=None):
        expected_url, expected_json = arguments.pop(0)
        assert expected_url == url
        if json is not None:
            assert expected_json["api_key"] == json["api_key"]
            if "teamspace" in expected_json:
                assert expected_json["teamspace"] == json["teamspace"]
                assert expected_json["cluster_id"] == json["cluster_id"]

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
    monkeypatch.setattr(file_endpoint_module, "_get_project", MagicMock())
    cluster_mock = MagicMock()
    cluster_mock.cluster_id = "cluster_id"
    monkeypatch.setattr(file_endpoint_module, "_get_cluster", MagicMock(return_value=cluster_mock))

    monkeypatch.setattr(file_endpoint_module, "LightningClient", MagicMock(return_value=lightning_client_mock))
    auth_mock = MagicMock()
    auth_mock.api_key = "api_key"
    monkeypatch.setattr(file_endpoint_module, "Auth", MagicMock(return_value=auth_mock))

    client = LLMFinetune(teamspace="teamspace")
    client.run(data_path=__file__)
