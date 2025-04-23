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


def test_invalid_format(monkeypatch, mock_model_data):
    mock_api = MagicMock()
    mock_api.list_models.return_value = mock_model_data
    monkeypatch.setattr("lightning_sdk.llm.llm.LLMApi", lambda: mock_api)

    with pytest.raises(ValueError, match="Model name must be in the format `organization/model_name`"):
        LLM("gpt-4o")


def test_invalid_provider(monkeypatch, mock_model_data):
    # Patch LLMApi to return mock model data
    mock_api = MagicMock()
    mock_api.list_models.return_value = mock_model_data
    monkeypatch.setattr("lightning_sdk.llm.llm.LLMApi", lambda: mock_api)

    with pytest.raises(
        ValueError, match=re.escape("Model provider openedai not found. Available models providers: ['openai']")
    ):
        LLM("openedai/gpt-4o")
