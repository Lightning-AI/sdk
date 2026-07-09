"""A tiny client for Lightning AI's chat/completions endpoint.

Lightning exposes an OpenAI-compatible gateway at ``/api/v1/chat/completions``
that authenticates with the *same* Lightning API key used for sandboxes, so the
whole example runs from a single ``sk-lit-...`` key -- no separate LLM provider
key required.

The endpoint supports OpenAI-style tool calling, including ``tool_choice`` to
force a function. We use that to get structured outputs (the ``Code`` and
``ExecutionEvaluation`` schemas the agent relies on).
"""

import json
import os
from typing import Any, Optional

import requests

# Lightning cloud URL. Read from LIGHTNING_CLOUD_URL if set, else the default.
DEFAULT_BASE_URL = "https://lightning.ai"


def _cloud_url() -> str:
    return os.environ.get("LIGHTNING_CLOUD_URL") or DEFAULT_BASE_URL


class LightningLLM:
    """Minimal client for ``POST {cloud_url}/api/v1/chat/completions``."""

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        temperature: Optional[float] = 0,
        timeout: int = 180,
    ):
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.api_key = (
            api_key
            or os.environ.get("LIGHTNING_SANDBOX_API_KEY")
            or os.environ.get("LIGHTNING_API_KEY")
        )
        if not self.api_key:
            raise ValueError(
                "No Lightning API key for the LLM endpoint. Pass api_key= or set "
                "LIGHTNING_SANDBOX_API_KEY / LIGHTNING_API_KEY."
            )
        self.url = _cloud_url().rstrip("/") + "/api/v1/chat/completions"

    def _messages(self, prompt: str, system: Optional[str]) -> list[dict]:
        messages: list[dict] = []
        if system:
            messages.append(
                {"role": "system", "content": [{"type": "text", "text": system}]}
            )
        messages.append(
            {"role": "user", "content": [{"type": "text", "text": prompt}]}
        )
        return messages

    def _post(self, payload: dict) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            self.url, headers=headers, data=json.dumps(payload), timeout=self.timeout
        )
        # Some models (e.g. gpt-5*) reject a non-default temperature. Retry once
        # without it rather than failing the whole graph.
        if (
            resp.status_code == 400
            and "temperature" in resp.text.lower()
            and "temperature" in payload
        ):
            payload = {k: v for k, v in payload.items() if k != "temperature"}
            resp = requests.post(
                self.url,
                headers=headers,
                data=json.dumps(payload),
                timeout=self.timeout,
            )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Lightning chat/completions error {resp.status_code}: {resp.text[:500]}"
            )
        return resp.json()

    def _base_payload(self, prompt: str, system: Optional[str]) -> dict:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._messages(prompt, system),
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        return payload

    def chat(self, prompt: str, system: Optional[str] = None) -> str:
        """Plain completion -> assistant message content."""
        data = self._post(self._base_payload(prompt, system))
        return data["choices"][0]["message"]["content"] or ""

    def call_tool(
        self,
        prompt: str,
        tool: dict,
        tool_name: str,
        system: Optional[str] = None,
    ) -> dict:
        """Force the model to call ``tool`` and return its parsed arguments."""
        payload = self._base_payload(prompt, system)
        payload["tools"] = [tool]
        payload["tool_choice"] = {"type": "function", "function": {"name": tool_name}}

        data = self._post(payload)
        message = data["choices"][0]["message"]
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            raise RuntimeError(
                f"Expected a tool call for {tool_name!r}, got content: "
                f"{message.get('content')!r}"
            )
        return json.loads(tool_calls[0]["function"]["arguments"])
