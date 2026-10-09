"""The models code.lightning.ai serves, as coding tools need to be told about them."""

from dataclasses import dataclass

CODE_BASE_URL = "https://code.lightning.ai/v1"
# OpenAI-compatible tools wait this long for a response before giving up
REQUEST_TIMEOUT_MS = 600_000
OUTPUT_TOKENS = 32_768


@dataclass(frozen=True)
class CodingModel:
    # the short name tool configs use for the model
    key: str
    id: str
    name: str
    context_window: int
    images: bool = False


# Keep in sync with lightning-ui's CodingUsage/harnesses.ts, which shows the same configs on the web.
CODING_MODELS = (
    CodingModel("glm-5.3", "lightning-ai/glm-5.3", "GLM-5.3", 1_048_576),
    CodingModel("glm-5.3-flash", "lightning-ai/glm-5.3-flash", "GLM-5.3 Flash", 253_952, images=True),
    CodingModel("deepseek-v4.1-flash", "lightning-ai/deepseek-v4.1-flash", "DeepSeek V4.1 Flash", 253_952),
)
# the model `lightning code setup` makes the default when the user has none
DEFAULT_MODEL = "deepseek-v4.1-flash"
MODEL_KEYS = tuple(model.key for model in CODING_MODELS)
