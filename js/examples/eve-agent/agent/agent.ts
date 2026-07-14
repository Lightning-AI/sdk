import { createAnthropic } from "@ai-sdk/anthropic";
import { defineAgent } from "eve";

const apiKey = process.env.LIGHTNING_SANDBOX_API_KEY ?? process.env.LIGHTNING_API_KEY;
if (!apiKey) {
  throw new Error("LIGHTNING_SANDBOX_API_KEY is required");
}

const lightning = createAnthropic({
  baseURL: "https://lightning.ai/v1",
  authToken: apiKey,
});

export default defineAgent({
  model: lightning("claude-opus-4-8"),
  reasoning: "high",
  limits: {
    maxOutputTokensPerSession: 40_000,
  },
});
