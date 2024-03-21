import lightning_sdk.services.file_endpoint as file_endpoint_module
from lightning_sdk.services import LLMFinetune
from unittest.mock import MagicMock


def test_llm_finetune(monkeypatch):
    requests_mock = MagicMock()

    arguments = [
        (
            "https://finetune-01hra53x9nzbhc774s2ecp7bcp.cloudspaces.litng.ai",
            {
                "model": "tiny-llama",
                "mode": "lora",
                "epochs": "3",
                "learning_rate": "0.0002",
                "micro_batch_size": "2",
                "global_batch_size": "8",
            },
        ),
        ("https://finetune-01hra53x9nzbhc774s2ecp7bcp.cloudspaces.litng.ai?upload_id=upload_id", None),
        ("https://finetune-01hra53x9nzbhc774s2ecp7bcp.cloudspaces.litng.ai?run_id=run_id", None),
        ("https://finetune-01hra53x9nzbhc774s2ecp7bcp.cloudspaces.litng.ai?run_id=run_id", None),
        ("https://finetune-01hra53x9nzbhc774s2ecp7bcp.cloudspaces.litng.ai?run_id=run_id", None),
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

    client = LLMFinetune(teamspace="")
    client.run(data_path=__file__)
