import asyncio
import base64
import datetime
import json
import os
import threading
import time
import warnings
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional, Union
from urllib.parse import urlencode

from rich.prompt import Confirm

from lightning_sdk.lightning_cloud import env
from lightning_sdk.lightning_cloud.login import Auth, AuthServer
from lightning_sdk.lightning_cloud.openapi.models import (
    StreamResultOfV1ConversationResponseChunk,
    V1ConversationResponseChunk,
    V1ManagedModel,
    V1ResponseChoice,
    V1ResponseChoiceDelta,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient

LITAI_CODE = os.environ.get("LITAI_CODE", "x334uv8t7v")


class _AuthServer(AuthServer):
    def __init__(self, model: str, *args: Any, **kwargs: Any) -> None:
        self._model = model
        super().__init__(*args, **kwargs)

    def get_auth_url(self, port: int) -> str:
        redirect_uri = f"http://localhost:{port}/login-complete"
        params = urlencode({"redirectTo": redirect_uri, "okbhrt": LITAI_CODE, "litaimodel": self._model})
        return f"{env.LIGHTNING_CLOUD_URL}/sign-in?{params}"


class _AuthLitAI(Auth):
    def __init__(self, model: str, shall_confirm: bool = False) -> None:
        super().__init__()
        self._model = model
        self._shall_confirm = shall_confirm

    def _run_server(self) -> None:
        if self._shall_confirm:
            proceed = Confirm.ask(
                "[bold yellow]LitAI needs to authenticate with Lightning AI.[/bold yellow]\n"
                "This will open a browser window for login.\n"
                "Do you want to continue?",
                default=True,
            )
            if not proceed:
                raise RuntimeError(
                    "Login cancelled. Please login at https://lightning.ai/sign-up. Or run `lightning login` to login."
                )
        print("Opening browser for authentication...")
        print("Please come back to the terminal after logging in.")
        time.sleep(1)
        _AuthServer(self._model).login_with_browser(self)


def authenticate(model: str, shall_confirm: bool = True) -> None:
    auth = _AuthLitAI(model, shall_confirm)
    auth.authenticate()


class LLMApi:
    """Internal API client for Lightning AI LLM (LitAI) conversation and model operations."""

    def __init__(self) -> None:
        self._client = LightningClient(retry=False, max_tries=0)
        self._assistant = None
        self._model = None

    def get_assistant(self, model_provider: str, model_name: str, user_name: str, org_name: str) -> str:
        """Resolve the assistant ID for a given managed model, caching the result on the instance.

        Args:
            model_provider: The provider of the managed model (e.g. ``"openai"``).
            model_name: The name of the managed model.
            user_name: The username context for the lookup.
            org_name: The organisation name context for the lookup.

        Returns:
            str: The assistant ID for the resolved managed model.
        """
        result = self._client.assistants_service_get_managed_model_assistant(
            model_provider=model_provider, model_name=model_name, user_name=user_name, org_name=org_name
        )
        self._assistant = result
        return result.id

    def get_model_metadata(self, teamspace_id: str, model_name: str) -> V1ManagedModel:
        """Return cached metadata for the managed model, fetching from the API on first call.

        Args:
            teamspace_id: The teamspace ID used to scope the model lookup.
            model_name: The name of the managed model to retrieve metadata for.

        Returns:
            V1ManagedModel: The managed model metadata.
        """
        if self._assistant and not self._model:
            self._model = self._client.assistants_service_get_managed_model_by_name(
                teamspace_id, self._assistant.managed_endpoint_id, model_name
            )
        return self._model

    def _parse_stream_line(self, decoded_line: str) -> Optional[V1ConversationResponseChunk]:
        """Parse a single ndjson line from a streaming response into a ``V1ConversationResponseChunk``.

        Args:
            decoded_line: A single UTF-8 decoded line from the streaming response body.

        Returns:
            Optional[V1ConversationResponseChunk]: The parsed chunk, or ``None`` if the line cannot be decoded.
        """
        try:
            payload = json.loads(decoded_line)
            result_data = payload.get("result", {})

            choices = []
            for choice in result_data.get("choices", []):
                delta = choice.get("delta", {})
                choices.append(
                    V1ResponseChoice(
                        delta=V1ResponseChoiceDelta(**delta),
                        finish_reason=choice.get("finishReason"),
                        index=choice.get("index"),
                    )
                )

            return V1ConversationResponseChunk(
                choices=choices,
                conversation_id=result_data.get("conversationId"),
                executable=result_data.get("executable"),
                id=result_data.get("id"),
                throughput=result_data.get("throughput"),
                stats=result_data.get("stats"),
                usage=result_data.get("usage"),
            )
        except json.JSONDecodeError:
            warnings.warn("Error decoding JSON:", decoded_line)
            return None

    def _stream_chat_response(
        self, result: StreamResultOfV1ConversationResponseChunk
    ) -> Generator[V1ConversationResponseChunk, None, None]:
        """Yield parsed ``V1ConversationResponseChunk`` objects from a streaming API result.

        Args:
            result: The raw streaming result object from the API client.

        Returns:
            Generator[V1ConversationResponseChunk, None, None]: Parsed response chunks.
        """
        for line in result.stream():
            decoded_lines = line.decode("utf-8").strip()
            for decoded_line in decoded_lines.splitlines():
                chunk = self._parse_stream_line(decoded_line)
                if chunk:
                    yield chunk

    def _encode_image_bytes_to_data_url(self, image: str) -> str:
        """Read a local image file and return it as a base64-encoded data URL.

        Args:
            image: Local filesystem path to the image file.

        Returns:
            str: A base64-encoded data URL of the form ``data:image/<ext>;base64,<data>``.
        """
        with open(image, "rb") as image_file:
            b64 = base64.b64encode(image_file.read()).decode("utf-8")
            extension = image.split(".")[-1]
            return f"data:image/{extension};base64,{b64}"

    def start_conversation(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_completion_tokens: Optional[int],
        assistant_id: str,
        images: Optional[List[str]] = None,
        conversation_id: Optional[str] = None,
        billing_project_id: Optional[str] = None,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        stream: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        reasoning_effort: Optional[str] = None,
        **kwargs: Any,
    ) -> Union[V1ConversationResponseChunk, Generator[V1ConversationResponseChunk, None, None]]:
        """Send a prompt to the assistant and return the response or a streaming generator.

        Args:
            prompt: The user message to send.
            system_prompt: Optional system prompt to set the assistant's behaviour.
            max_completion_tokens: Maximum number of tokens to generate.
            assistant_id: The assistant ID to send the message to.
            images: Optional list of local image paths or HTTP URLs to include.
            conversation_id: ID of an existing conversation to continue; ``None`` starts a new one.
            billing_project_id: Project ID for billing attribution.
            name: Optional name for a new conversation.
            metadata: Optional key-value metadata to attach to the conversation.
            stream: When ``True``, return a generator of response chunks.
            tools: Optional list of tool definitions to pass to the model.
            reasoning_effort: Optional reasoning effort level for supported models.
            **kwargs: Additional fields forwarded to the request body.

        Returns:
            Union[V1ConversationResponseChunk, Generator[V1ConversationResponseChunk, None, None]]:
            A single response chunk when ``stream=False``, or a generator of chunks when ``stream=True``.
        """
        is_internal_conversation = os.getenv("LIGHTNING_INTERNAL_CONVERSATION", "false").lower() == "true"
        ephemeral = os.getenv("LIGHTNING_EPHEMERAL", "false").lower() == "true"
        if ephemeral:
            conversation_id = None
            name = None
        body = {
            "message": {
                "author": {"role": "user"},
                "content": [
                    {"contentType": "text", "parts": [prompt]},
                ],
            },
            "conversation_id": conversation_id,
            "billing_project_id": billing_project_id,
            "name": name,
            "stream": stream,
            "metadata": metadata or {},
            "internal_conversation": is_internal_conversation,
            "system_prompt": system_prompt,
            "ephemeral": ephemeral,
            "parent_conversation_id": kwargs.get("parent_conversation_id", ""),
            "parent_message_id": kwargs.get("parent_message_id", ""),
            "tools": tools,
        }
        if max_completion_tokens is not None:
            body["max_completion_tokens"] = max_completion_tokens

        if reasoning_effort:
            body["reasoning_effort"] = reasoning_effort

        if images:
            for image in images:
                url = image
                if not image.startswith("http"):
                    url = self._encode_image_bytes_to_data_url(image)

                body["message"]["content"].append(
                    {
                        "contentType": "image",
                        "parts": [url],
                    }
                )

        result = self._client.assistants_service_start_conversation(body, assistant_id, _preload_content=not stream)
        if not stream:
            return result.result
        return self._stream_chat_response(result)

    async def async_start_conversation(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_completion_tokens: Optional[int],
        assistant_id: str,
        images: Optional[List[str]] = None,
        conversation_id: Optional[str] = None,
        billing_project_id: Optional[str] = None,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        stream: bool = False,
        reasoning_effort: Optional[str] = None,
        **kwargs: Any,
    ) -> Union[V1ConversationResponseChunk, AsyncGenerator[V1ConversationResponseChunk, None]]:
        """Async variant of ``start_conversation``; returns a response or an async streaming generator.

        Args:
            prompt: The user message to send.
            system_prompt: Optional system prompt to set the assistant's behaviour.
            max_completion_tokens: Maximum number of tokens to generate.
            assistant_id: The assistant ID to send the message to.
            images: Optional list of local image paths or HTTP URLs to include.
            conversation_id: ID of an existing conversation to continue; ``None`` starts a new one.
            billing_project_id: Project ID for billing attribution.
            name: Optional name for a new conversation.
            metadata: Optional key-value metadata to attach to the conversation.
            stream: When ``True``, return an async generator of response chunks.
            reasoning_effort: Optional reasoning effort level for supported models.
            **kwargs: Additional fields forwarded to the request body.

        Returns:
            Union[V1ConversationResponseChunk, AsyncGenerator[V1ConversationResponseChunk, None]]:
            A single response chunk when ``stream=False``, or an async generator of chunks when ``stream=True``.
        """
        is_internal_conversation = os.getenv("LIGHTNING_INTERNAL_CONVERSATION", "false").lower() == "true"
        ephemeral = os.getenv("LIGHTNING_EPHEMERAL", "false").lower() == "true"
        if ephemeral:
            conversation_id = None
            name = None
        body = {
            "message": {
                "author": {"role": "user"},
                "content": [
                    {"contentType": "text", "parts": [prompt]},
                ],
            },
            "conversation_id": conversation_id,
            "billing_project_id": billing_project_id,
            "name": name,
            "stream": stream,
            "metadata": metadata or {},
            "internal_conversation": is_internal_conversation,
            "system_prompt": system_prompt,
            "ephemeral": ephemeral,
            "parent_conversation_id": kwargs.get("parent_conversation_id", ""),
            "parent_message_id": kwargs.get("parent_message_id", ""),
            "sent_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds"),
        }
        if max_completion_tokens is not None:
            body["max_completion_tokens"] = max_completion_tokens

        if reasoning_effort:
            body["reasoning_effort"] = reasoning_effort

        if images:
            for image in images:
                url = image
                if not image.startswith("http"):
                    url = self._encode_image_bytes_to_data_url(image)

                body["message"]["content"].append(
                    {
                        "contentType": "image",
                        "parts": [url],
                    }
                )

        if not stream:
            thread = await asyncio.to_thread(
                self._client.assistants_service_start_conversation, body, assistant_id, async_req=True
            )
            result = await asyncio.to_thread(thread.get)
            return result.result

        conversation_thread = await asyncio.to_thread(
            self._client.assistants_service_start_conversation,
            body,
            assistant_id,
            async_req=True,
            _preload_content=False,
        )

        return self.stream_response(conversation_thread)

    async def stream_response(self, thread: Any) -> AsyncGenerator[V1ConversationResponseChunk, None]:
        """Yield ``V1ConversationResponseChunk`` objects from a background thread running a streaming API call.

        Args:
            thread: An async thread result object whose ``.get()`` returns the raw streaming response.

        Returns:
            AsyncGenerator[V1ConversationResponseChunk, None]: Parsed response chunks streamed asynchronously.
        """
        loop = asyncio.get_event_loop()
        response = await asyncio.to_thread(thread.get)

        queue = asyncio.Queue()

        def enqueue() -> None:
            try:
                for line in response:
                    decoded_lines = line.decode("utf-8").strip()
                    for decoded_line in decoded_lines.splitlines():
                        chunk = self._parse_stream_line(decoded_line)
                        if chunk:
                            asyncio.run_coroutine_threadsafe(queue.put(chunk), loop)
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)

        threading.Thread(target=enqueue, daemon=True).start()

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

    def list_conversations(self, assistant_id: str) -> List[str]:
        """Return all conversation IDs for the given assistant.

        Args:
            assistant_id: The assistant whose conversations to list.

        Returns:
            List[str]: The list of conversation IDs.
        """
        result = self._client.assistants_service_list_conversations(assistant_id)
        return result.conversations

    def get_conversation(self, assistant_id: str, conversation_id: str) -> V1ConversationResponseChunk:
        """Fetch all messages for a specific conversation.

        Args:
            assistant_id: The assistant that owns the conversation.
            conversation_id: The unique ID of the conversation to retrieve.

        Returns:
            V1ConversationResponseChunk: The messages in the conversation.
        """
        result = self._client.assistants_service_get_conversation(assistant_id, conversation_id)
        return result.messages

    def reset_conversation(self, assistant_id: str, conversation_id: str) -> None:
        """Delete a conversation and all its messages.

        Args:
            assistant_id: The assistant that owns the conversation.
            conversation_id: The unique ID of the conversation to delete.
        """
        self._client.assistants_service_delete_conversation(assistant_id, conversation_id)
