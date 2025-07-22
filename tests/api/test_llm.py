from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk.api.llm_api import LLMApi
from lightning_sdk.lightning_cloud.openapi.models import V1ConversationResponseChunk


@pytest.fixture()
def mock_client():
    """Mock the LightningClient."""
    with patch("lightning_sdk.api.llm_api.LightningClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture()
def llm_api(mock_client):
    """Create a fresh LLMApi instance for each test with mocked client."""
    return LLMApi()


@pytest.fixture()
def sample_response():
    """Create a sample conversation response."""
    response = MagicMock()
    response.result = MagicMock(spec=V1ConversationResponseChunk)
    return response


def test_start_conversation_basic(llm_api, mock_client, sample_response):
    """Test basic conversation start with minimal parameters."""
    # Arrange
    mock_client.assistants_service_start_conversation.return_value = sample_response

    # Act
    llm_api.start_conversation(
        prompt="Hello, how are you?", system_prompt=None, max_completion_tokens=5, assistant_id="assistant-123"
    )

    # Assert
    mock_client.assistants_service_start_conversation.assert_called_once()
    call_args = mock_client.assistants_service_start_conversation.call_args

    # Check the body structure
    body = call_args[0][0]  # First positional argument
    assert body["message"]["author"]["role"] == "user"
    assert body["message"]["content"][0]["contentType"] == "text"
    assert body["message"]["content"][0]["parts"] == ["Hello, how are you?"]
    assert body["max_tokens"] == 5
    assert body["conversation_id"] is None
    assert body["billing_project_id"] is None
    assert body["name"] is None
    assert body["stream"] is False
    assert body["metadata"] == {}
    assert body["internal_conversation"] is False
    assert body["system_prompt"] is None
    assert body["ephemeral"] is False
    assert body["parent_conversation_id"] == ""
    assert body["parent_message_id"] == ""
    assert body["tools"] is None

    # Check assistant_id parameter
    assert call_args[0][1] == "assistant-123"
    assert call_args[1]["_preload_content"] is True
