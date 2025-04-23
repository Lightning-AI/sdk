from typing import Dict, List, Set, Tuple

from lightning_sdk.api.llm_api import LLMApi


class LLM:
    def __init__(self, name: str) -> None:
        self._name = name
        self._org, self._model_name = self._parse_model_name(name)
        self._llm_api = LLMApi()
        self._models = self._build_model_lookup(self._llm_api.list_models())
        self._model_exists()

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
