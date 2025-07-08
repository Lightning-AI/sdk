import json
import os
from typing import Any, AsyncGenerator, ClassVar, Dict, Generator, List, Optional, Tuple, Union

from lightning_sdk.api.llm_api import LLMApi
from lightning_sdk.lightning_cloud.openapi.models.v1_conversation_response_chunk import V1ConversationResponseChunk

PUBLIC_MODEL_PROVIDERS: Dict[str, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
}


def _load_public_assistants() -> Dict[str, str]:
    """Load public assistants from a JSON file."""
    try:
        json_path = os.path.join(os.path.dirname(__file__), "public_assistants.json")
        with open(json_path) as f:
            return json.load(f)
    except Exception as e:
        print(f"[warning] Failed to load public_assistants.json: {e}")
        return {}


class LLM:
    _auth_info_cached: ClassVar[bool] = False
    _cached_auth_info: ClassVar[Dict[str, Optional[str]]] = {}
    _llm_api_cache: ClassVar[Dict[Optional[str], LLMApi]] = {}
    _public_assistants: ClassVar[Optional[Dict[str, str]]] = None

    def __new__(cls, name: str, teamspace: Optional[str] = None, enable_async: Optional[bool] = False) -> "LLM":
        return super().__new__(cls)

    def __init__(
        self,
        name: str,
        teamspace: Optional[str] = None,
        enable_async: Optional[bool] = False,
    ) -> None:
        """Initializes the LLM instance with teamspace information, which is required for billing purposes.

        Teamspace information is resolved through the following methods:
        1. `.lightning/credentials.json` - Attempts to retrieve the teamspace from the local credentials file.
        2. Environment Variables - Checks for `LIGHTNING_*` environment variables.
        3. User Authentication - Redirects the user to the login page if teamspace information is not found.

        Args:
            name (str): The name of the model or resource.
            teamspace (Optional[str]): The specified teamspace for billing. If not provided, it will be resolved
                                       through the above methods.
            enable_async (Optional[bool]): Enable async requests

        Raises:
            ValueError: If teamspace information cannot be resolved.
        """
        # TODO support user input teamspace
        self._get_auth_info()

        self._model_provider, self._model_name = self._parse_model_name(name)
        self._enable_async = enable_async

        # Reuse LLMApi per teamspace (as billing is based on teamspace)
        if teamspace not in LLM._llm_api_cache:
            LLM._llm_api_cache[teamspace] = LLMApi()
        self._llm_api = LLM._llm_api_cache[teamspace]

        self._model_id = self._get_model_id()
        self._conversations = {}

    @property
    def name(self) -> str:
        return self._model_name

    @property
    def provider(self) -> str:
        return self._model_provider

    def _get_auth_info(self) -> None:
        if not LLM._auth_info_cached:
            teamspace_name = os.environ.get("LIGHTNING_TEAMSPACE", None)
            if teamspace_name is None:
                raise ValueError(
                    "Teamspace name must be provided either through "
                    "the environment variable LIGHTNING_TEAMSPACE or as an argument."
                )
            LLM._cached_auth_info = {
                "teamspace_name": teamspace_name,
                "teamspace_id": os.environ.get("LIGHTNING_CLOUD_PROJECT_ID", None),
                "user_name": os.environ.get("LIGHTNING_USERNAME", ""),
                "user_id": os.environ.get("LIGHTNING_USER_ID", None),
                "org_name": os.environ.get("LIGHTNING_ORG", ""),
                "cloud_url": os.environ.get("LIGHTNING_CLOUD_URL", None),
            }
            LLM._auth_info_cached = True
            if LLM._public_assistants is None:
                LLM._public_assistants = _load_public_assistants()
        # Always assign to the current instance
        self._teamspace_name = LLM._cached_auth_info["teamspace_name"]
        self._teamspace_id = LLM._cached_auth_info["teamspace_id"]
        self._user_name = LLM._cached_auth_info["user_name"]
        self._user_id = LLM._cached_auth_info["user_id"]
        self._org_name = LLM._cached_auth_info["org_name"]
        self._cloud_url = LLM._cached_auth_info["cloud_url"]
        self._org = None

    def _parse_model_name(self, name: str) -> Tuple[str, str]:
        parts = name.split("/")
        if len(parts) == 1:
            # a user model or a org model
            return None, parts[0]
        if len(parts) == 2:
            return parts[0].lower(), parts[1]
        raise ValueError(
            f"Model name must be in the format `organization/model_name` or `model_name`, but got '{name}'."
        )

    # returns the assistant ID
    def _get_model_id(self) -> str:
        if self._model_provider in PUBLIC_MODEL_PROVIDERS:
            # if prod
            if (
                self._cloud_url == "https://lightning.ai"
                and LLM._public_assistants
                and f"{self._model_provider}/{self._model_name}" in LLM._public_assistants
            ):
                return LLM._public_assistants[f"{self._model_provider}/{self._model_name}"]
            try:
                return self._llm_api.get_assistant(
                    model_provider=PUBLIC_MODEL_PROVIDERS[self._model_provider],
                    model_name=self._model_name,
                    user_name="",
                    org_name="",
                )
            except Exception as e:
                raise ValueError(
                    f"Public model '{self._model_provider}/{self._model_name}' not found. "
                    "Please check the model name or provider."
                ) from e

        # Try organization model
        try:
            return self._llm_api.get_assistant(
                model_provider="",
                model_name=self._model_name,
                user_name="",
                org_name=self._model_provider,
            )
        except Exception:
            pass

        # Try user model
        try:
            return self._llm_api.get_assistant(
                model_provider="",
                model_name=self._model_name,
                user_name=self._model_provider,
                org_name="",
            )
        except Exception as user_error:
            raise ValueError(
                f"Model '{self._model_provider}/{self._model_name}' not found as either an org or user model.\n"
            ) from user_error

    def _get_conversations(self) -> None:
        conversations = self._llm_api.list_conversations(assistant_id=self._model_id)
        for conversation in conversations:
            if conversation.name and conversation.name not in self._conversations:
                self._conversations[conversation.name] = conversation.id

    def _stream_chat_response(
        self, result: Generator[V1ConversationResponseChunk, None, None], conversation: Optional[str] = None
    ) -> Generator[str, None, None]:
        first_line = next(result, None)
        if first_line:
            if conversation and first_line.conversation_id:
                self._conversations[conversation] = first_line.conversation_id
            yield first_line.choices[0].delta.content

        for line in result:
            yield line.choices[0].delta.content

    async def _async_stream_text(self, output: str) -> AsyncGenerator[str, None]:
        async for chunk in output:
            if chunk.choices and chunk.choices[0].delta:
                yield chunk.choices[0].delta.content

    async def _async_chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_completion_tokens: Optional[int] = 500,
        images: Optional[Union[List[str], str]] = None,
        conversation: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> Union[str, AsyncGenerator[str, None]]:
        conversation_id = self._conversations.get(conversation) if conversation else None
        output = await self._llm_api.async_start_conversation(
            prompt=prompt,
            system_prompt=system_prompt,
            max_completion_tokens=max_completion_tokens,
            images=images,
            assistant_id=self._model_id,
            conversation_id=conversation_id,
            billing_project_id=self._teamspace_id,
            metadata=metadata,
            name=conversation,
            stream=stream,
            **kwargs,
        )
        if not stream:
            if conversation and not conversation_id:
                self._conversations[conversation] = output.conversation_id
            return output.choices[0].delta.content
        return self._async_stream_text(output)

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_completion_tokens: Optional[int] = 500,
        images: Optional[Union[List[str], str]] = None,
        conversation: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> Union[str, Generator[str, None, None]]:
        if conversation and conversation not in self._conversations:
            self._get_conversations()

        if images:
            if isinstance(images, str):
                images = [images]
            for image in images:
                if not isinstance(image, str):
                    raise NotImplementedError(f"Image type {type(image)} are not supported yet.")

        conversation_id = self._conversations.get(conversation) if conversation else None

        if self._enable_async:
            return self._async_chat(
                prompt,
                system_prompt,
                max_completion_tokens,
                images,
                conversation,
                metadata,
                stream,
                **kwargs,
            )

        output = self._llm_api.start_conversation(
            prompt=prompt,
            system_prompt=system_prompt,
            max_completion_tokens=max_completion_tokens,
            images=images,
            assistant_id=self._model_id,
            conversation_id=conversation_id,
            billing_project_id=self._teamspace_id,
            metadata=metadata,
            name=conversation,
            stream=stream,
            **kwargs,
        )
        if not stream:
            if conversation and not conversation_id:
                self._conversations[conversation] = output.conversation_id
            return output.choices[0].delta.content
        return self._stream_chat_response(output, conversation=conversation)

    def list_conversations(self) -> List[Dict]:
        self._get_conversations()
        return list(self._conversations.keys())

    def _get_conversation_messages(self, conversation_id: str) -> Optional[str]:
        return self._llm_api.get_conversation(assistant_id=self._model_id, conversation_id=conversation_id)

    def get_history(self, conversation: str) -> Optional[List[Dict]]:
        if conversation not in self._conversations:
            self._get_conversations()

        if conversation not in self._conversations:
            raise ValueError(
                f"Conversation '{conversation}' not found. \nAvailable conversations: {self._conversations.keys()}"
            )

        messages = self._get_conversation_messages(self._conversations[conversation])
        history = []
        for message in messages:
            if message.author.role == "user":
                history.append({"role": "user", "content": message.content[0].parts[0]})
            elif message.author.role == "assistant":
                history.append({"role": "assistant", "content": message.content[0].parts[0]})
        return history

    def reset_conversation(self, conversation: str) -> None:
        if conversation not in self._conversations:
            self._get_conversations()
        if conversation in self._conversations:
            self._llm_api.reset_conversation(
                assistant_id=self._model_id,
                conversation_id=self._conversations[conversation],
            )
            del self._conversations[conversation]
