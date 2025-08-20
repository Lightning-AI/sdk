import os
from typing import Any, AsyncGenerator, ClassVar, Dict, Generator, List, Optional, Tuple, Union

from lightning_sdk.api import TeamspaceApi, UserApi
from lightning_sdk.api.llm_api import LLMApi, authenticate
from lightning_sdk.lightning_cloud.openapi.models.v1_conversation_response_chunk import V1ConversationResponseChunk
from lightning_sdk.llm.public_assistants import PUBLIC_MODELS
from lightning_sdk.utils.resolve import _resolve_org, _resolve_teamspace

PUBLIC_MODEL_PROVIDERS: Dict[str, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "lightning-ai": "lightning-ai",
}


class LLM:
    _auth_info_cached: ClassVar[bool] = False
    _cached_auth_info: ClassVar[Dict[str, Optional[str]]] = {}
    _llm_api_cache: ClassVar[Dict[Optional[str], LLMApi]] = {}
    _public_assistants: ClassVar[Optional[Dict[str, Dict[str, Any]]]] = None

    def __new__(cls, name: str, teamspace: Optional[str] = None, enable_async: Optional[bool] = False) -> "LLM":
        return super().__new__(cls)

    def __init__(
        self,
        name: str,
        teamspace: Optional[str] = None,
        enable_async: Optional[bool] = False,
    ) -> None:
        """Initializes the LLM instance with teamspace information, which is required for billing purposes.

        Args:
            name (str): The name of the model or resource.
            teamspace (Optional[str]): The specified teamspace for billing. If not provided, it will
                                        use the available default teamspace.
            enable_async (Optional[bool]): Enable async requests

        Raises:
            ValueError: If teamspace information cannot be resolved.
        """
        teamspace_name = None
        teamspace_owner = None
        if teamspace:
            if "/" in teamspace:
                try:
                    teamspace_owner, teamspace_name = teamspace.split("/", maxsplit=1)
                except ValueError as e:
                    raise ValueError(
                        f"Invalid teamspace format: '{teamspace}'. "
                        "Teamspace should be specified as '{org}/{teamspace_name}' or '{org}'"
                        "(e.g., 'my-org/my-teamspace', 'my-org')."
                    ) from e
            else:
                # org is given
                teamspace_name = teamspace

        self._model_provider, self._model_name = self._parse_model_name(name)
        self._get_auth_info(teamspace_owner, teamspace_name)

        self._enable_async = enable_async

        # Reuse LLMApi per teamspace (as billing is based on teamspace)
        if teamspace not in LLM._llm_api_cache:
            LLM._llm_api_cache[teamspace] = LLMApi()
        self._llm_api = LLM._llm_api_cache[teamspace]

        self._context_length = None
        self._model_id = self._get_model_id()
        self._conversations = {}

    @property
    def name(self) -> str:
        return self._model_name

    @property
    def provider(self) -> str:
        return self._model_provider

    def context_length(self, model: Optional[str] = None) -> Optional[int]:
        if model is None:
            return self._context_length

        context_info = self._public_assistants.get(model)
        if context_info is None or "context_length" not in context_info:
            raise ValueError(f"Cannot access context length of model '{model}'.")

        return int(context_info["context_length"])

    def _get_auth_info(self, teamspace_owner: Optional[str] = None, teamspace_name: Optional[str] = None) -> None:
        if not LLM._auth_info_cached:
            if teamspace_owner and teamspace_name:
                # org with specific teamspace
                try:
                    t = _resolve_teamspace(teamspace=teamspace_name, org=None, user=teamspace_owner)
                except Exception:
                    try:
                        t = _resolve_teamspace(teamspace=teamspace_name, org=teamspace_owner, user=None)
                    except Exception as err:
                        raise ValueError(
                            f"Teamspace {teamspace_owner}/{teamspace_name} not found."
                            "Please verify owner name (username or organization) and the teamspace name are correct."
                        ) from err

                    os.environ["LIGHTNING_TEAMSPACE"] = t.name
                    os.environ["LIGHTNING_CLOUD_PROJECT_ID"] = t.id

            elif teamspace_name and teamspace_owner is None:
                # if only org name is given, use the default teamspace
                try:
                    org = _resolve_org(teamspace_name)
                    teamspace_api = TeamspaceApi()
                    teamspace = teamspace_api.list_teamspaces(org.id)[0]

                except Exception as err:
                    raise ValueError(
                        f"Organization {teamspace_name} not found. Please verify the organization name."
                    ) from err
                os.environ["LIGHTNING_CLOUD_PROJECT_ID"] = teamspace.id
                os.environ["LIGHTNING_TEAMSPACE"] = teamspace.name

            else:
                if teamspace_name is None:
                    # studio users
                    teamspace_name = os.environ.get("LIGHTNING_TEAMSPACE", None)

                if teamspace_name is None:
                    # local users with no given teamspace
                    try:
                        authenticate(model=f"{self.provider}/{self.name}")
                        teamspace_api = TeamspaceApi()
                        user_api = UserApi()
                        authed_user = user_api._client.auth_service_get_user()
                        default_teamspace = teamspace_api.list_teamspaces(owner_id=authed_user.id)[0]
                        teamspace_name = default_teamspace.name
                        teamspace_id = default_teamspace.id
                        os.environ["LIGHTNING_CLOUD_PROJECT_ID"] = teamspace_id
                        os.environ["LIGHTNING_TEAMSPACE"] = teamspace_name
                    except Exception as err:
                        # throw an appropriate error that guides users to login through the platform
                        raise ValueError(
                            "Teamspace information is missing. "
                            "If this is your first time using LitAI, please log in at https://lightning.ai/sign-up "
                            "and re-run your script, or set environment variable LIGHTNING_TEAMSPACE=<your-teamspace>."
                        ) from err

            # TODO: if LIGHTNING_CLOUD_PROJECT_ID does not exist, we have to get the id from the teamspace name

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
                LLM._public_assistants = PUBLIC_MODELS
        # Always assign to the current instance
        self._teamspace_name = LLM._cached_auth_info["teamspace_name"]
        self._teamspace_id = LLM._cached_auth_info["teamspace_id"]
        self._user_name = LLM._cached_auth_info["user_name"]
        self._user_id = LLM._cached_auth_info["user_id"]
        self._org_name = LLM._cached_auth_info["org_name"]
        self._cloud_url = LLM._cached_auth_info["cloud_url"]
        self._org = None

    @staticmethod
    def _parse_model_name(name: str) -> Tuple[str, str]:
        """Parses the model name into provider and model name.

        >>> LLM._parse_model_name("openai/v1/gpt-3.5-turbo")
        ('openai', 'v1/gpt-3.5-turbo')
        """
        if "/" not in name:
            raise ValueError(
                f"Invalid model name format: '{name}'. "
                "Model name must be in the format `provider/model_name`."
                "(e.g., 'lightning-ai/gpt-oss-20b')"
            )
        provider, model_name = name.split("/", maxsplit=1)
        return provider.lower(), model_name

    # returns the assistant ID
    def _get_model_id(self) -> str:
        if self._model_provider in PUBLIC_MODEL_PROVIDERS:
            # if prod
            if (
                self._cloud_url == "https://lightning.ai"
                and LLM._public_assistants
                and f"{self._model_provider}/{self._model_name}" in LLM._public_assistants
            ):
                self._context_length = int(
                    LLM._public_assistants[f"{self._model_provider}/{self._model_name}"]["context_length"]
                )
                return LLM._public_assistants[f"{self._model_provider}/{self._model_name}"]["id"]
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

        if self._model_provider == "lightning-ai":
            # Try model provider model
            try:
                return self._llm_api.get_assistant(
                    model_provider=self._model_provider,
                    model_name=self._model_name,
                    user_name="",
                    org_name="",
                )
            except Exception:
                pass

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
        self,
        result: Generator[V1ConversationResponseChunk, None, None],
        conversation: Optional[str] = None,
        full_response: bool = False,
    ) -> Generator[str, None, None]:
        first_line = next(result, None)
        if first_line:
            if conversation and first_line.conversation_id:
                self._conversations[conversation] = first_line.conversation_id
            if full_response:
                yield first_line
            else:
                yield first_line.choices[0].delta.content

        for line in result:
            if full_response:
                yield line
            else:
                yield line.choices[0].delta.content

    async def _async_stream_text(self, output: str, full_response: bool = False) -> AsyncGenerator[str, None]:
        async for chunk in output:
            if chunk.choices and chunk.choices[0].delta:
                if full_response:
                    yield chunk
                else:
                    yield chunk.choices[0].delta.content

    async def _async_chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_completion_tokens: Optional[int] = None,
        images: Optional[Union[List[str], str]] = None,
        conversation: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        stream: bool = False,
        full_response: bool = False,
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
            if full_response:
                return output
            return output.choices[0].delta.content
        return self._async_stream_text(output, full_response)

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_completion_tokens: Optional[int] = None,
        images: Optional[Union[List[str], str]] = None,
        conversation: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        stream: bool = False,
        full_response: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Union[
        V1ConversationResponseChunk, Generator[V1ConversationResponseChunk, None, None], str, Generator[str, None, None]
    ]:
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
                full_response,
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
            tools=tools,
            **kwargs,
        )
        if not stream:
            if conversation and not conversation_id:
                self._conversations[conversation] = output.conversation_id
            if full_response:
                return output
            return output.choices[0].delta.content
        return self._stream_chat_response(output, conversation=conversation, full_response=full_response)

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
