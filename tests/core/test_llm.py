import re
from unittest.mock import MagicMock

import pytest

from lightning_sdk.llm import LLM


@pytest.fixture()
def mock_model_data():
    model_meta = MagicMock()
    model_meta.name = "gpt-4o"

    endpoint = MagicMock()
    endpoint.id = "openai"
    endpoint.models_metadata = [model_meta]

    return [endpoint]


@pytest.fixture()
def mock_public_model():
    public_model_meta = MagicMock()
    public_model_meta.model = "gpt-4o"
    public_model_meta.id = "ast_123"
    return [public_model_meta]


def test_invalid_format(monkeypatch, mock_model_data):
    mock_api = MagicMock()
    mock_api.list_models.return_value = mock_model_data
    monkeypatch.setattr("lightning_sdk.llm.llm.LLMApi", lambda: mock_api)

    with pytest.raises(ValueError, match="Model name must be in the format `organization/model_name`"):
        LLM("gpt-4o")


def test_invalid_provider(monkeypatch, mock_model_data):
    mock_api = MagicMock()
    mock_api.list_models.return_value = mock_model_data
    monkeypatch.setattr("lightning_sdk.llm.llm.LLMApi", lambda: mock_api)

    with pytest.raises(
        ValueError, match=re.escape("Model provider openedai not found. Available models providers: ['openai']")
    ):
        LLM("openedai/gpt-4o")


def test_chat(monkeypatch, mock_model_data, mock_public_model):
    mock_api = MagicMock()
    mock_api.list_models.return_value = mock_model_data
    mock_api.get_public_models.return_value = mock_public_model
    monkeypatch.setattr("lightning_sdk.llm.llm.LLMApi", lambda: mock_api)

    mock_response = MagicMock()
    mock_response.choices[0].delta.content = "I'm doing well, thank you!"
    mock_api.start_conversation.return_value = mock_response

    llm = LLM("openai/gpt-4o")
    response = llm.chat("Hello, how are you?")

    assert isinstance(response, str)
    assert response == "I'm doing well, thank you!"
