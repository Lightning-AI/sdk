/**
 * Build a LangChain chat model backed by Lightning AI's LLM gateway.
 *
 * Lightning exposes an OpenAI-compatible gateway at `{cloudUrl}/api/v1` that
 * authenticates with the *same* Lightning API key used for sandboxes, so the
 * whole example runs from a single `sk-lit-...` key -- no separate LLM provider
 * key required. Because it speaks the OpenAI wire format, we can drive it with
 * the standard LangChain `ChatOpenAI` integration simply by pointing `baseURL`
 * at it; everything downstream (`bindTools`, `withStructuredOutput`, LCEL
 * chains) then works exactly as it would against OpenAI.
 */
import { ChatOpenAI } from "@langchain/openai";

// Default Lightning cloud URL; overridden by LIGHTNING_CLOUD_URL when set.
const DEFAULT_CLOUD_URL = "https://lightning.ai";

function apiBase(): string {
  const cloudUrl = process.env.LIGHTNING_CLOUD_URL || DEFAULT_CLOUD_URL;
  return cloudUrl.replace(/\/+$/, "") + "/api/v1";
}

function resolveApiKey(apiKey?: string): string {
  const key =
    apiKey ||
    process.env.LIGHTNING_SANDBOX_API_KEY ||
    process.env.LIGHTNING_API_KEY;
  if (!key) {
    throw new Error(
      "No Lightning API key for the LLM gateway. Pass apiKey or set " +
        "LIGHTNING_SANDBOX_API_KEY / LIGHTNING_API_KEY.",
    );
  }
  return key;
}

/** Return a `ChatOpenAI` wired to Lightning's OpenAI-compatible gateway. */
export function makeChatModel(
  model: string,
  {
    apiKey,
    temperature = 0.0,
    timeout = 180_000,
  }: { apiKey?: string; temperature?: number; timeout?: number } = {},
): ChatOpenAI {
  return new ChatOpenAI({
    model,
    apiKey: resolveApiKey(apiKey),
    temperature,
    timeout,
    configuration: {
      baseURL: apiBase(),
    },
    // The JS `ChatOpenAI` defaults `top_p`/`frequency_penalty`/`presence_penalty`
    // to concrete values and always sends them; the Python SDK leaves them unset.
    // Lightning's gateway rejects `top_p` for some models (e.g. Claude), so strip
    // these here to match Python's "only send what you set" behavior. (Values are
    // spread last into the request and `undefined` keys are dropped on the wire.)
    modelKwargs: {
      top_p: undefined,
      frequency_penalty: undefined,
      presence_penalty: undefined,
    },
  });
}
