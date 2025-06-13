from unittest.mock import AsyncMock, MagicMock

import pytest

from lightning_sdk.llm import AsyncLLM


@pytest.fixture()
def mock_auth(monkeypatch):
    mock_auth = MagicMock()
    mock_auth.id = "user-123"
    mock_auth.name = "user-name"

    monkeypatch.setattr("lightning_sdk.llm.llm._get_authed_user", lambda: mock_auth)

    mock_org = MagicMock()
    mock_org.id = "org-123"
    mock_org.name = "org-name"
    monkeypatch.setattr("lightning_sdk.llm.llm._resolve_org", lambda org: mock_org)

    mock_menu = MagicMock()
    mock_possible_teamspaces = {
        "teamspace-123": {"name": "teamspace-123", "org": None, "user": "user-name"},
    }

    monkeypatch.setattr("lightning_sdk.llm.llm._resolve_teamspace", lambda *args, **kwargs: None)

    mock_menu._get_possible_teamspaces.return_value = mock_possible_teamspaces

    monkeypatch.setattr("lightning_sdk.llm.llm._TeamspacesMenu", lambda: mock_menu)

    teamspace = MagicMock()
    teamspace.id = "teamspace-123"
    teamspace.name = "teamspace-123"
    teamspace.owner = mock_org
    monkeypatch.setattr("lightning_sdk.llm.llm.Teamspace", lambda **kwargs: teamspace)
    return mock_menu


@pytest.fixture()
def mock_public_model():
    public_model_meta = MagicMock()
    public_model_meta.model = "gpt-4o"
    public_model_meta.id = "ast_123"
    return [public_model_meta]


@pytest.mark.asyncio()
async def test_chat_returns_expected_output(monkeypatch, mock_auth, mock_public_model):
    mock_api = MagicMock()
    mock_api.list_models.return_value = mock_public_model
    mock_api.get_public_models.return_value = mock_public_model
    monkeypatch.setattr("lightning_sdk.llm.llm.LLMApi", lambda: mock_api)

    # Setup mock model
    llm = AsyncLLM(name="gpt-4o")
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
