import re
from unittest.mock import MagicMock

import pytest

from lightning_sdk.llm import LLM


@pytest.fixture()
def mock_auth(monkeypatch):
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

    mock_org = MagicMock()
    mock_org.id = "org-123"
    mock_org.name = "org-name"
    monkeypatch.setattr("lightning_sdk.llm.llm._resolve_org", lambda org: mock_org)
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
def mock_org_model():
    org_model_meta = MagicMock()
    org_model_meta.model = "org-model1"
    org_model_meta.id = "ast_234"
    org_model_meta.org_id = "org-123"
    return [org_model_meta]


@pytest.fixture()
def mock_user_model():
    user_model_meta = MagicMock()
    user_model_meta.model = "user-model1"
    user_model_meta.id = "ast_456"
    user_model_meta.user_id = "user-123"
    return [user_model_meta]


def test_invalid_format(monkeypatch, mock_auth, mock_model_data):
    mock_api = MagicMock()
    mock_api.list_models.return_value = mock_model_data
    monkeypatch.setattr("lightning_sdk.llm.llm.LLMApi", lambda: mock_api)

    with pytest.raises(
        ValueError,
        match="Model name must be in the format `organization/model_name` or `model_name`, but got 'openai/gpt-4o/v1'",
    ):
        LLM("openai/gpt-4o/v1")


def test_org_model(monkeypatch, mock_auth, mock_org_model):
    mock_org = MagicMock()
    mock_org.id = "org-123"
    mock_org.name = "org-name"
    monkeypatch.setattr("lightning_sdk.llm.llm._resolve_org", lambda org: mock_org)

    mock_api = MagicMock()
    mock_api.get_org_models.return_value = mock_org_model
    monkeypatch.setattr("lightning_sdk.llm.llm.LLMApi", lambda: mock_api)

    llm = LLM("org-name/org-model1")
    assert llm._org.id == "org-123"

    llm = LLM("org-model1", org="org-name")
    assert llm._org.id == "org-123"

    with pytest.raises(
        ValueError,
        match=re.escape("Model 'dummy-model' not found. \nAvailable models: \nOrg (org-name) Models: org-model1"),
    ):
        LLM("org-123/dummy-model")


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
        match=re.escape("Model 'dummy-model' not found. \nAvailable models: \nUser (mockuser) Models: user-model1"),
    ):
        LLM("dummy-model", user="mockuser")


def test_chat(monkeypatch, mock_auth, mock_model_data, mock_public_model):
    mock_api = MagicMock()
    mock_api.list_models.return_value = mock_model_data
    mock_api.get_public_models.return_value = mock_public_model
    monkeypatch.setattr("lightning_sdk.llm.llm.LLMApi", lambda: mock_api)

    mock_response = MagicMock()
    mock_response.conversation_id = "conv_123"
    mock_response.choices[0].delta.content = "I'm doing well, thank you!"
    mock_api.start_conversation.return_value = mock_response

    llm = LLM("openai/gpt-4o")
    response = llm.chat("Hello, how are you?")

    assert isinstance(response, str)
    assert response == "I'm doing well, thank you!"

    # explicitly pass max_tokens
    response = llm.chat("Hello, how are you?", max_completion_tokens=10)
    mock_api.start_conversation.assert_called_with(
        prompt="Hello, how are you?",
        system_prompt=None,
        max_completion_tokens=10,
        assistant_id=llm._model.id,
        conversation_id=None,
    )

    # pass conversation and continue conversation
    assert "conv1" not in llm._conversations
    continue_response = llm.chat("Hello, how are you?", conversation="conv1")
    assert isinstance(continue_response, str)
    mock_api.start_conversation.assert_called_with(
        prompt="Hello, how are you?",
        system_prompt=None,
        max_completion_tokens=500,
        assistant_id=llm._model.id,
        conversation_id=None,
    )
    mock_api.start_conversation.reset_mock()
    continue_response = llm.chat("Hi again!", conversation="conv1")
    assert isinstance(continue_response, str)
    mock_api.start_conversation.assert_called_with(
        prompt="Hi again!",
        system_prompt=None,
        max_completion_tokens=500,
        assistant_id=llm._model.id,
        conversation_id="conv_123",
    )
    # check list of conversations
    assert llm._conversations == {"conv1": "conv_123"}
    assert llm.list_conversations() == ["conv1"]

    # get history of conv1
    user_msg = MagicMock()
    user_msg.conversation_id = "conv_123"
    user_msg.author.role = "user"
    user_msg.content = [MagicMock(parts=["Hello!"])]

    assistant_msg = MagicMock()
    assistant_msg.conversation_id = "conv_123"
    assistant_msg.author.role = "assistant"
    assistant_msg.content = [MagicMock(parts=["Hi there!"])]

    llm._get_conversation_messages = MagicMock(return_value=[user_msg, assistant_msg])

    history = llm.get_history("conv1")

    assert history == [
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi there!"},
    ]

    # reset conversation
    llm.reset_conversation("conv1")
    assert "conv1" not in llm._conversations
