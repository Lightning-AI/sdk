"""The models code.lightning.ai serves, as coding tools need to be told about them."""

from dataclasses import dataclass
from typing import Any, Optional

import requests

CODE_BASE_URL = "https://code.lightning.ai/v1"
# OpenAI-compatible tools wait this long for a response before giving up
REQUEST_TIMEOUT_MS = 600_000
# the model `lightning code setup` makes the default when the user has none
DEFAULT_MODEL = "deepseek-v4.1-flash"
_FETCH_TIMEOUT_S = 10


@dataclass(frozen=True)
class CodingModel:
    # the short name tool configs use for the model
    key: str
    id: str
    name: str
    context_window: int
    output_tokens: int
    images: bool = False
    tools: bool = True
    reasoning: bool = True


# Used when /v1/models can't be reached; matches what it served on 2026-10-09.
FALLBACK_MODELS = (
    CodingModel("glm-5.3", "lightning-ai/glm-5.3", "GLM-5.3", 1_048_576, 131_072),
    CodingModel("glm-5.3-flash", "lightning-ai/glm-5.3-flash", "GLM-5.3 Flash", 253_952, 131_072, images=True),
    CodingModel(
        "deepseek-v4.1-flash", "lightning-ai/deepseek-v4.1-flash", "DeepSeek V4.1 Flash", 253_952, 131_072, images=True
    ),
)


def _parse(entry: Any) -> Optional[CodingModel]:
    """Read one OpenRouter-style /v1/models entry, or None when it lacks what a tool config needs."""
    if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
        return None
    model_id = entry["id"]
    provider = entry.get("top_provider") or {}
    context = entry.get("context_length") or provider.get("context_length")
    output = provider.get("max_completion_tokens")
    if not isinstance(context, int) or not isinstance(output, int):
        return None
    inputs = (entry.get("architecture") or {}).get("input_modalities") or ["text"]
    parameters = entry.get("supported_parameters")
    return CodingModel(
        key=model_id.split("/", 1)[-1],
        id=model_id,
        name=entry.get("name") or model_id,
        context_window=context,
        output_tokens=output,
        images="image" in inputs,
        # an entry that doesn't list its parameters is assumed to support them, as every model does today
        tools=parameters is None or "tools" in parameters,
        reasoning=parameters is None or "reasoning_effort" in parameters,
    )


def fetch_models() -> tuple[CodingModel, ...]:
    """The models /v1/models lists right now. Raises when it can't be read or lists none."""
    response = requests.get(f"{CODE_BASE_URL}/models", timeout=_FETCH_TIMEOUT_S)
    response.raise_for_status()
    models = tuple(model for model in map(_parse, response.json().get("data") or []) if model is not None)
    if not models:
        raise ValueError("it listed no models")
    return models


def coding_models() -> tuple[tuple[CodingModel, ...], Optional[str]]:
    """The models to configure, and why the built-in list was used instead of /v1/models, if it was."""
    try:
        return fetch_models(), None
    except Exception as exc:
        return FALLBACK_MODELS, str(exc) or type(exc).__name__


def default_model(models: tuple[CodingModel, ...]) -> str:
    keys = [model.key for model in models]
    return DEFAULT_MODEL if DEFAULT_MODEL in keys else keys[0]
