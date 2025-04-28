import re
from unittest.mock import MagicMock

import pytest

from lightning_sdk.llm import LLM


@pytest.fixture()
def mock_user_auth(monkeypatch):
    mock_auth = MagicMock()
    mock_auth.user_id = "user-123"
    monkeypatch.setattr("lightning_sdk.llm.llm.Auth", lambda: mock_auth)

    mock_user_data = MagicMock()
    mock_user_data.username = "mockuser"
    mock_user_api_instance = MagicMock()
    mock_user_api_instance._get_user_by_id.return_value = mock_user_data
    monkeypatch.setattr("lightning_sdk.llm.llm.UserApi", lambda: mock_user_api_instance)
    monkeypatch.setattr("lightning_sdk.user.UserApi", lambda: mock_user_api_instance)

    mock_user_instance = MagicMock()
    monkeypatch.setattr("lightning_sdk.llm.llm.User", lambda name: mock_user_instance)
    return mock_user_instance


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


@pytest.fixture()
def mock_user_model():
    user_model_meta = MagicMock()
    user_model_meta.model = "user-model1"
    user_model_meta.id = "ast_456"
    user_model_meta.user_id = "user-123"
    return [user_model_meta]


def test_invalid_format(monkeypatch, mock_user_auth, mock_model_data):
    mock_api = MagicMock()
    mock_api.list_models.return_value = mock_model_data
    monkeypatch.setattr("lightning_sdk.llm.llm.LLMApi", lambda: mock_api)

    with pytest.raises(
        ValueError,
        match="Model name must be in the format `organization/model_name` or `model_name`, but got 'openai/gpt-4o/v1'",
    ):
        LLM("openai/gpt-4o/v1")


def test_user_model(monkeypatch, mock_user_model):
    mock_auth = MagicMock()
    mock_auth.user_id = "user-123"
    monkeypatch.setattr("lightning_sdk.llm.llm.Auth", lambda: mock_auth)

    mock_user_data = MagicMock()
    mock_user_data.username = "mockuser"
    mock_user_api_instance = MagicMock()
    mock_user_api_instance._get_user_by_id.return_value = mock_user_data
    monkeypatch.setattr("lightning_sdk.llm.llm.UserApi", lambda: mock_user_api_instance)
    monkeypatch.setattr("lightning_sdk.user.UserApi", lambda: mock_user_api_instance)

    mock_user_instance = MagicMock()
    mock_user_instance.id = "user-123"
    mock_user_instance.name = "mockuser"
    monkeypatch.setattr("lightning_sdk.llm.llm.User", lambda name: mock_user_instance)

    mock_api = MagicMock()
    mock_api.get_user_models.return_value = mock_user_model
    monkeypatch.setattr("lightning_sdk.llm.llm.LLMApi", lambda: mock_api)

    monkeypatch.setattr("lightning_sdk.llm.llm._resolve_user", lambda user: user)

    llm = LLM("user-model1", user="mockuser")
    assert llm._model_name == "user-model1"
    with pytest.raises(
        ValueError,
        match=re.escape(
            "Model dummy-model not found in public or mockuser models. \
                Available models: ['user-model1']"
        ),
    ):
        LLM("dummy-model", user="mockuser")


def test_chat(monkeypatch, mock_user_auth, mock_model_data, mock_public_model):
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

    # explicitly pass max_tokens
    response = llm.chat("Hello, how are you?", max_tokens=10)
    mock_api.start_conversation.assert_called_with("Hello, how are you?", None, 10, llm._model.id)
