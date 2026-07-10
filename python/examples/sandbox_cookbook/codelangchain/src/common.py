"""Shared configuration and utilities for the coding agent.

The LangGraph "brain" runs locally, so this module only holds the shared graph
state, terminal colors, and the configuration describing the *sandbox* in which
the agent's generated code is executed.
"""

from typing import Any, Dict, TypedDict

# --- LLM configuration -----------------------------------------------------
# The agent's "brain" is a standard LangChain ``ChatOpenAI`` model pointed at
# Lightning's OpenAI-compatible gateway (see src/llm.py), authenticated with the
# same Lightning API key used for sandboxes -- so no separate LLM provider key
# is needed. Any model id from the gateway's catalog works here.
MODEL = "anthropic/claude-opus-4-8"
DEBUG_MODEL = "lightning-ai/deepseek-v4-pro"

# --- Sandbox configuration -------------------------------------------------
# The agent executes its generated code inside a Lightning sandbox. Lightning
# runtimes ship Python *or* Node, never the heavy ML stack, so we install the
# libraries the agent is expected to use (torch + transformers) at create time.
SANDBOX_RUNTIME = "python313"
SANDBOX_INSTANCE_TYPE = "cpu-4"  # 4 vCPU / 16 GB -- enough for CPU gpt2 inference
SANDBOX_STORAGE_GB = 20  # room for the torch wheel + cached HF models

# Installed into the sandbox before the agent runs any code. We pull the CPU
# build of torch from the PyTorch index (the default PyPI wheel bundles CUDA
# and is huge / pointless on a CPU sandbox).
SANDBOX_SETUP_SCRIPT = (
    "set -eux; "
    "pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "
    "'torch==2.5.0'; "
    "pip install --no-cache-dir 'transformers==4.46.0'"
)


class GraphState(TypedDict):
    """Represents the state of our graph.

    Attributes:
        keys: A dictionary where each key is a string.
    """

    keys: Dict[str, Any]


COLOR = {
    "HEADER": "\033[95m",
    "BLUE": "\033[94m",
    "GREEN": "\033[92m",
    "RED": "\033[91m",
    "ENDC": "\033[0m",
}
