from typing import Dict, List, Optional, Set, Tuple, Union

from lightning_sdk.api import UserApi
from lightning_sdk.api.llm_api import LLMApi
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi import V1Assistant
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.organization import Organization
from lightning_sdk.user import User
from lightning_sdk.utils.resolve import _resolve_org, _resolve_user


class LLM:
    def __init__(
        self,
        name: str,
        user: Union[str, "User", None] = None,
        org: Union[str, "Organization", None] = None,
    ) -> None:
        self._auth = Auth()
        self._user = None

        try:
            self._auth.authenticate()
            self._user = User(name=UserApi()._get_user_by_id(self._auth.user_id).username)
        except ConnectionError as e:
            raise e

        self._name = name
        try:
            self._user = _resolve_user(self._user or user)
        except ValueError:
            self._user = None

        self._name = name
        self._org, self._model_name = self._parse_model_name(name)
        try:
            # check if it is a org model
            self._org = _resolve_org(self._org or org)
        except ApiException:
            self._org = None

        self._llm_api = LLMApi()
        self._public_models = self._build_model_lookup(self._get_public_models())
        self._org_models = self._build_model_lookup(self._get_org_models())
        self._user_models = self._build_model_lookup(self._get_user_models())
        self._model = self._get_model()
        self._conversations = {}

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

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_completion_tokens: Optional[int] = 500,
        conversation: Optional[str] = None,
    ) -> str:
        conversation_id = self._conversations.get(conversation) if conversation else None
        output = self._llm_api.start_conversation(
            prompt=prompt,
            system_prompt=system_prompt,
            max_completion_tokens=max_completion_tokens,
            assistant_id=self._model.id,
            conversation_id=conversation_id,
        )
        if conversation and not conversation_id:
            self._conversations[conversation] = output.conversation_id
        return output.choices[0].delta.content

    def list_conversations(self) -> List[Dict]:
        return list(self._conversations.keys())
