import re
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.llm import LLM


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("LIGHTNING_TEAMSPACE", "teamspace-name")
    monkeypatch.setenv("LIGHTNING_CLOUD_PROJECT_ID", "teamspace-123")
    monkeypatch.setenv("LIGHTNING_USERNAME", "user-name")
    monkeypatch.setenv("LIGHTNING_USER_ID", "user-123")
    return monkeypatch


@pytest.fixture()
def mock_auth(monkeypatch):
    mock_org = MagicMock()
    mock_org.id = "org-123"
    mock_org.name = "org-name"
    mock_org_api = MagicMock()
    mock_org_api.get_org.return_value = mock_org
    monkeypatch.setattr("lightning_sdk.llm.llm._resolve_org", lambda org: mock_org)
    monkeypatch.setattr("lightning_sdk.llm.llm.OrgApi", lambda: mock_org_api)

    mock_teamspace = MagicMock()
    mock_teamspace.id = "teamspace-123"
    mock_teamspace.name = "teamspace-name"
    mock_teamspace.owner = mock_org
    mock_teamspace_api = MagicMock()
    mock_teamspace_api._get_teamspace_by_id.return_value = mock_teamspace
    monkeypatch.setattr("lightning_sdk.llm.llm.TeamspaceApi", lambda: mock_teamspace_api)
    return mock_teamspace


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
    mock_api = MagicMock()
    mock_api.get_org_models.return_value = mock_org_model
    monkeypatch.setattr("lightning_sdk.llm.llm.LLMApi", lambda: mock_api)

    llm = LLM("org-name/org-model1")
    assert llm._org.id == "org-123"
    assert llm.owner.name == "org-name"
    assert llm.provider == "org-name"

    with pytest.raises(
        ValueError,
        match=re.escape("Model 'dummy-model' not found. \nAvailable models: \nOrg (org-name) Models: org-model1"),
    ):
        LLM("org-123/dummy-model")


def test_invalid_org(monkeypatch, mock_auth, mock_public_model, mock_org_model):
    # there could be a case where the model provider is an org that exists, however, the user does not have access to it
    # then it would make sense to search for whatever they have availabe in public, teamspace and org

    mock_api = MagicMock()
    mock_get_org = MagicMock()
    mock_get_org.side_effect = [ApiException("Unauthorized user"), mock_org_model]
    monkeypatch.setattr(LLM, "_get_org_models", mock_get_org)
    mock_api.get_public_models.return_value = mock_public_model
    monkeypatch.setattr("lightning_sdk.llm.llm.LLMApi", lambda: mock_api)

    warning_message = (
        "User is not authenticated to access the model in organization: 'wrong-org'.\n"
        " Proceeding with appropriate org models, user models, or public models."
    )
    with pytest.warns(UserWarning, match=re.escape(warning_message)):
        LLM("wrong-org/gpt-4o")


def test_user_model(monkeypatch, mock_user_model):
    mock_api = MagicMock()
    mock_api.get_user_models.return_value = mock_user_model
    monkeypatch.setattr("lightning_sdk.llm.llm.LLMApi", lambda: mock_api)
    user = MagicMock()
    user.name = "user-name"
    user.id = "user-123"

    mock_teamspace = MagicMock()
    mock_teamspace.id = "teamspace-123"
    mock_teamspace.name = "teamspace-name"
    mock_teamspace.owner = user
    mock_teamspace_api = MagicMock()
    mock_teamspace_api._get_teamspace_by_id.return_value = mock_teamspace
    monkeypatch.setattr("lightning_sdk.llm.llm.TeamspaceApi", lambda: mock_teamspace_api)

    llm = LLM("user-name/user-model1")
    assert llm.owner.name == "user-name"
    assert llm.name == "user-model1"
    assert llm.provider == "user-name"

    with pytest.raises(
        ValueError,
        match=re.escape("Model 'dummy-model' not found. \nAvailable models: \nUser (user-name) Models: user-model1"),
    ):
        LLM("dummy-model", teamspace="user-name/teamspace-123")


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
    response = llm.chat("Hello, how are you?", max_completion_tokens=10, metadata={"user_api": "123456"})
    mock_api.start_conversation.assert_called_with(
        prompt="Hello, how are you?",
        system_prompt=None,
        max_completion_tokens=10,
        assistant_id=llm._model.id,
        images=None,
        conversation_id=None,
        billing_project_id="teamspace-123",
        name=None,
        stream=False,
        metadata={"user_api": "123456"},
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
        images=None,
        conversation_id=None,
        billing_project_id="teamspace-123",
        name="conv1",
        stream=False,
        metadata=None,
    )
    mock_api.start_conversation.reset_mock()
    continue_response = llm.chat("Hi again!", conversation="conv1")
    assert isinstance(continue_response, str)
    mock_api.start_conversation.assert_called_with(
        prompt="Hi again!",
        system_prompt=None,
        max_completion_tokens=500,
        assistant_id=llm._model.id,
        images=None,
        conversation_id="conv_123",
        billing_project_id="teamspace-123",
        name="conv1",
        stream=False,
        metadata=None,
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

    # test streaming
    llm = LLM("openai/gpt-4o")
    response = llm.chat("Hello, how are you?", stream=True)

    assert isinstance(response, Generator)
    mock_api.start_conversation.assert_called_with(
        prompt="Hello, how are you?",
        system_prompt=None,
        max_completion_tokens=500,
        assistant_id=llm._model.id,
        images=None,
        conversation_id=None,
        billing_project_id="teamspace-123",
        name=None,
        stream=True,
        metadata=None,
    )

    # test image content type
    llm = LLM("openai/gpt-4o")
    response = llm.chat(
        "Describe the image",
        images="https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg",
    )
    mock_api.start_conversation.assert_called_with(
        prompt="Describe the image",
        system_prompt=None,
        max_completion_tokens=500,
        assistant_id=llm._model.id,
        images=[
            "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
        ],
        conversation_id=None,
        billing_project_id="teamspace-123",
        name=None,
        stream=False,
        metadata=None,
    )

    # local images
    llm = LLM("openai/gpt-4o")
    response = llm.chat(
        "Describe the image",
        images=["/home/user/image.jpg", "/home/user/image2.png", "/home/user/image3.jpeg"],
    )
    mock_api.start_conversation.assert_called_with(
        prompt="Describe the image",
        system_prompt=None,
        max_completion_tokens=500,
        assistant_id=llm._model.id,
        images=["/home/user/image.jpg", "/home/user/image2.png", "/home/user/image3.jpeg"],
        conversation_id=None,
        billing_project_id="teamspace-123",
        name=None,
        stream=False,
        metadata=None,
    )

    # system prompt
    response = llm.chat(
        "Hello, how are you?", system_prompt="user prompt", max_completion_tokens=10, metadata={"user_api": "123456"}
    )
    mock_api.start_conversation.assert_called_with(
        prompt="Hello, how are you?",
        system_prompt="user prompt",
        max_completion_tokens=10,
        assistant_id=llm._model.id,
        images=None,
        conversation_id=None,
        billing_project_id="teamspace-123",
        name=None,
        stream=False,
        metadata={"user_api": "123456"},
    )


def test_chat_backend(monkeypatch, mock_auth, mock_public_model):
    mock_api = MagicMock()
    mock_api.get_public_models.return_value = mock_public_model
    monkeypatch.setattr("lightning_sdk.llm.llm.LLMApi", lambda: mock_api)

    mock_conv1 = MagicMock()
    mock_conv1.name = "test1"
    mock_conv1.id = "conv_123"
    mock_api.list_conversations.return_value = [mock_conv1]

    llm1 = LLM("openai/gpt-4o")
    llm1.chat("Hello, how are you?", conversation="test1")

    llm2 = LLM("openai/gpt-4o")
    llm2.list_conversations()

    # should be able to retrieve conversation "test1"
    conversations = llm2.list_conversations()
    assert set(conversations) == {"test1"}


@pytest.mark.asyncio()
async def test_async_chat(monkeypatch, mock_auth, mock_model_data, mock_public_model):
    mock_api = MagicMock()
    mock_api.list_models.return_value = mock_model_data
    mock_api.get_public_models.return_value = mock_public_model
    monkeypatch.setattr("lightning_sdk.llm.llm.LLMApi", lambda: mock_api)

    llm = LLM(name="gpt-4o", enable_async=True)

    llm._model = MagicMock()
    llm._model.id = "model-id"
    llm._teamspace = MagicMock()
    llm._teamspace.id = "teamspace-id"
    llm._conversations = {}

    # Setup mock output
    mock_output = MagicMock()
    mock_output.choices = [MagicMock(delta=MagicMock(content="Hello!"))]
    mock_output.conversation_id = "new-conv-id"

    llm._llm_api = MagicMock()
    llm._llm_api.async_start_conversation = AsyncMock(return_value=mock_output)

    # Call chat
    result = await llm.chat("Hi", conversation="test-convo")

    # Assertions
    llm._llm_api.async_start_conversation.assert_awaited_once()
    assert result == "Hello!"
    assert llm._conversations["test-convo"] == "new-conv-id"


@pytest.mark.asyncio()
async def test_async_stream_chat(monkeypatch, mock_auth, mock_model_data, mock_public_model):
    mock_api = MagicMock()
    mock_api.list_models.return_value = mock_model_data
    mock_api.get_public_models.return_value = mock_public_model
    monkeypatch.setattr("lightning_sdk.llm.llm.LLMApi", lambda: mock_api)
    llm = LLM(name="gpt-4o", enable_async=True)

    llm._model = MagicMock()
    llm._model.id = "model-id"
    llm._teamspace = MagicMock()
    llm._teamspace.id = "teamspace-id"
    llm._conversations = {}

    async def mock_stream_response(*args, **kwargs):
        for chunk in ["Hello", ", ", "world", "!"]:
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content=chunk))])

    llm._llm_api = MagicMock()
    llm._llm_api.async_start_conversation = AsyncMock(return_value=mock_stream_response())

    # Call chat
    result = ""
    async for token in await llm.chat("Hi there", stream=True, conversation="test"):
        result += token
    assert result == "Hello, world!"
    llm._llm_api.async_start_conversation.assert_awaited_once()
