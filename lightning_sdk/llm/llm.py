import os
import warnings
from typing import AsyncGenerator, Dict, Generator, List, Optional, Set, Tuple, Union

from lightning_sdk.api.llm_api import LLMApi
from lightning_sdk.cli.teamspace_menu import _TeamspacesMenu
from lightning_sdk.lightning_cloud.openapi import V1Assistant
from lightning_sdk.lightning_cloud.openapi.models.v1_conversation_response_chunk import V1ConversationResponseChunk
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.organization import Organization
from lightning_sdk.owner import Owner
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.utils.resolve import _get_authed_user, _resolve_org, _resolve_teamspace


class LLM:
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
        menu = _TeamspacesMenu()
        user = _get_authed_user()
        possible_teamspaces = menu._get_possible_teamspaces(user)
        if teamspace is None:
            # get current teamspace
            self._teamspace = _resolve_teamspace(teamspace=None, org=None, user=None)
        else:
            self._teamspace = Teamspace(**menu._get_teamspace_from_name(teamspace, possible_teamspaces))

        if self._teamspace is None:
            # select the first available teamspace
            first_teamspace = next(iter(possible_teamspaces.values()), None)

            if first_teamspace:
                self._teamspace = Teamspace(
                    name=first_teamspace["name"],
                    org=first_teamspace["org"],
                    user=first_teamspace["user"],
                )
                warnings.warn(
                    f"No teamspace given. Using teamspace: {self._teamspace.name}.",
                    UserWarning,
                    stacklevel=2,
                )

        if self._teamspace is None:
            raise ValueError("Teamspace is required for billing but could not be resolved. ")

        self._user = user

        self._model_provider, self._model_name = self._parse_model_name(name)

        self._llm_api = LLMApi()
        self._enable_async = enable_async

        try:
            # check if it is a org model
            self._org = _resolve_org(self._model_provider)

            try:
                # check if user has access to the org
                self._org_models = self._build_model_lookup(self._get_org_models())
            except ApiException:
                warnings.warn(
                    f"User is not authenticated to access the model in organization: '{self._model_provider}'.\n"
                    " Proceeding with appropriate org models, user models, or public models.",
                    UserWarning,
                    stacklevel=2,
                )
                self._model_provider = None
                raise
        except ApiException:
            if isinstance(self._teamspace.owner, Organization):
                self._org = self._teamspace.owner
            else:
                self._org = None
            self._org_models = self._build_model_lookup(self._get_org_models())

        self._public_models = self._build_model_lookup(self._get_public_models())
        self._user_models = self._build_model_lookup(self._get_user_models())
        self._model = self._get_model()
        self._conversations = {}

    @property
    def name(self) -> str:
        return self._model_name

    @property
    def provider(self) -> str:
        return self._model_provider

    @property
    def owner(self) -> Optional[Owner]:
        return self._teamspace.owner

    def _parse_model_name(self, name: str) -> Tuple[str, str]:
        parts = name.split("/")
        if len(parts) == 1:
            # a user model or a org model
            return None, parts[0]
        if len(parts) == 2:
            return parts[0], parts[1]
        raise ValueError(
            f"Model name must be in the format `organization/model_name` or `model_name`, but got '{name}'."
        )

    def _build_model_lookup(self, endpoints: List[str]) -> Dict[str, Set[str]]:
        result = {}
        for endpoint in endpoints:
            result.setdefault(endpoint.model, []).append(endpoint)
        return result

    def _get_public_models(self) -> List[str]:
        return self._llm_api.get_public_models()

    def _get_org_models(self) -> List[str]:
        return self._llm_api.get_org_models(self._org.id) if self._org else []

    def _get_user_models(self) -> List[str]:
        return self._llm_api.get_user_models(self._user.id) if self._user else []

    def _get_model(self) -> V1Assistant:
        # TODO how to handle multiple models with same model type? For now, just use the first one
        if self._model_name in self._public_models:
            return self._public_models.get(self._model_name)[0]
        if self._model_name in self._org_models:
            return self._org_models.get(self._model_name)[0]
        if self._model_name in self._user_models:
            return self._user_models.get(self._model_name)[0]

        available_models = []
        if self._public_models:
            available_models.append(f"Public Models: {', '.join(self._public_models.keys())}")

        if self._org and self._org_models:
            available_models.append(f"Org ({self._org.name}) Models: {', '.join(self._org_models.keys())}")

        if self._user and self._user_models:
            available_models.append(f"User ({self._user.name}) Models: {', '.join(self._user_models.keys())}")

        available_models_str = "\n".join(available_models)
        raise ValueError(f"Model '{self._model_name}' not found. \nAvailable models: \n{available_models_str}")

    def _get_conversations(self) -> None:
        conversations = self._llm_api.list_conversations(assistant_id=self._model.id)
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
        upload_local_images: bool = False,
    ) -> Union[str, AsyncGenerator[str, None]]:
        conversation_id = self._conversations.get(conversation) if conversation else None
        output = await self._llm_api.async_start_conversation(
            prompt=prompt,
            system_prompt=system_prompt,
            max_completion_tokens=max_completion_tokens,
            images=images,
            assistant_id=self._model.id,
            conversation_id=conversation_id,
            billing_project_id=self._teamspace.id,
            metadata=metadata,
            name=conversation,
            stream=stream,
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
        upload_local_images: bool = False,
    ) -> Union[str, Generator[str, None, None]]:
        if conversation and conversation not in self._conversations:
            self._get_conversations()

        if images:
            if isinstance(images, str):
                images = [images]
            for image in images:
                if not isinstance(image, str):
                    raise NotImplementedError(f"Image type {type(image)} are not supported yet.")
                if not image.startswith("http") and upload_local_images:
                    self._teamspace.upload_file(file_path=image, remote_path=f"images/{os.path.basename(image)}")

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
                upload_local_images,
            )

        output = self._llm_api.start_conversation(
            prompt=prompt,
            system_prompt=system_prompt,
            max_completion_tokens=max_completion_tokens,
            images=images,
            assistant_id=self._model.id,
            conversation_id=conversation_id,
            billing_project_id=self._teamspace.id,
            metadata=metadata,
            name=conversation,
            stream=stream,
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
        return self._llm_api.get_conversation(assistant_id=self._model.id, conversation_id=conversation_id)

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
                assistant_id=self._model.id,
                conversation_id=self._conversations[conversation],
            )
            del self._conversations[conversation]
