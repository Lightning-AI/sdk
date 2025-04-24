from typing import Dict, List, Optional, Set, Tuple

from lightning_sdk.api.llm_api import LLMApi
from lightning_sdk.lightning_cloud.openapi import V1Assistant


class LLM:
    def __init__(self, name: str) -> None:
        self._name = name
        self._org, self._model_name = self._parse_model_name(name)
        self._llm_api = LLMApi()
        self._models = self._build_model_lookup(self._llm_api.list_models())
        self._model_exists()
        self._public_models = self._build_public_model_lookup(self._get_public_models())
        self._model = self._get_model()

    def _parse_model_name(self, name: str) -> Tuple[str, str]:
        parts = name.split("/")
        if len(parts) != 2:
            raise ValueError(f"Model name must be in the format `organization/model_name`, but got '{name}'.")
        return parts[0], parts[1]

    def _build_model_lookup(self, endpoints: List[str]) -> Dict[str, Set[str]]:
        return {endpoint.id: {model.name for model in endpoint.models_metadata} for endpoint in endpoints}

    def _model_exists(self) -> bool:
        if self._org not in self._models:
            raise ValueError(
                f"Model provider {self._org} not found. Available models providers: {list(self._models.keys())}"
            )

        if self._model_name not in self._models[self._org]:
            raise ValueError(
                f"Model {self._model_name} not found. Available models by {self._org}: {self._models[self._org]}"
            )
        return True

    def _build_public_model_lookup(self, endpoints: List[str]) -> Dict[str, Set[str]]:
        result = {}
        for endpoint in endpoints:
            result.setdefault(endpoint.model, []).append(endpoint)
        return result

    def _get_public_models(self) -> List[str]:
        return self._llm_api.get_public_models()

    def _get_model(self, public_model: bool = True) -> V1Assistant:
        # TODO figure out how to identify if model is public or not
        if not public_model:
            raise NotImplementedError("Non-public models are not supported yet.")
        # TODO how to handle multiple models with same model type? For now, just use the first one
        return self._public_models.get(self._model_name)[0]

    def chat(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        output = self._llm_api.start_conversation(prompt, system_prompt, self._model.id)
        return output.choices[0].delta.content
