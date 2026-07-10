"""Build a LangChain chat model backed by Lightning AI's LLM gateway.

Lightning exposes an OpenAI-compatible gateway at ``{cloud_url}/api/v1`` that
authenticates with the *same* Lightning API key used for sandboxes, so the whole
example runs from a single ``sk-lit-...`` key -- no separate LLM provider key
required. Because it speaks the OpenAI wire format, we can drive it with the
standard LangChain ``ChatOpenAI`` integration simply by pointing ``base_url`` at
it; everything downstream (``bind_tools``, ``with_structured_output``, LCEL
chains) then works exactly as it would against OpenAI.
"""

import os
from typing import Optional

from langchain_openai import ChatOpenAI

# Default Lightning cloud URL; overridden by LIGHTNING_CLOUD_URL when set.
DEFAULT_CLOUD_URL = "https://lightning.ai"


def _api_base() -> str:
    cloud_url = os.environ.get("LIGHTNING_CLOUD_URL") or DEFAULT_CLOUD_URL
    return cloud_url.rstrip("/") + "/api/v1"


def _resolve_api_key(api_key: Optional[str]) -> str:
    key = (
        api_key
        or os.environ.get("LIGHTNING_SANDBOX_API_KEY")
        or os.environ.get("LIGHTNING_API_KEY")
    )
    if not key:
        raise ValueError(
            "No Lightning API key for the LLM gateway. Pass api_key= or set "
            "LIGHTNING_SANDBOX_API_KEY / LIGHTNING_API_KEY."
        )
    return key


def make_chat_model(
    model: str,
    api_key: Optional[str] = None,
    temperature: float = 0.0,
    timeout: int = 180,
) -> ChatOpenAI:
    """Return a ``ChatOpenAI`` wired to Lightning's OpenAI-compatible gateway."""
    return ChatOpenAI(
        model=model,
        api_key=_resolve_api_key(api_key),
        base_url=_api_base(),
        temperature=temperature,
        timeout=timeout,
    )
