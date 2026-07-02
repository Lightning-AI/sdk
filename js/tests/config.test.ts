import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, it } from "node:test";
import {
  DEFAULT_LIGHTNING_BASE_URL,
  getApiKey,
  getBaseUrl,
  mergeSandboxConfig,
  resetSandboxConfig,
} from "../src/config.js";

describe("config", () => {
  const savedEnv = {
    LIGHTNING_API_KEY: process.env.LIGHTNING_API_KEY,
    LIGHTNING_CLOUD_URL: process.env.LIGHTNING_CLOUD_URL,
  };

  beforeEach(() => {
    resetSandboxConfig();
    delete process.env.LIGHTNING_API_KEY;
    delete process.env.LIGHTNING_CLOUD_URL;
  });

  afterEach(() => {
    resetSandboxConfig();
    if (savedEnv.LIGHTNING_API_KEY !== undefined) {
      process.env.LIGHTNING_API_KEY = savedEnv.LIGHTNING_API_KEY;
    } else {
      delete process.env.LIGHTNING_API_KEY;
    }
    if (savedEnv.LIGHTNING_CLOUD_URL !== undefined) {
      process.env.LIGHTNING_CLOUD_URL = savedEnv.LIGHTNING_CLOUD_URL;
    } else {
      delete process.env.LIGHTNING_CLOUD_URL;
    }
  });

  describe("getApiKey", () => {
    it("throws when no key is configured", () => {
      assert.throws(() => getApiKey(), /Missing API key/);
    });

    it("uses explicit override first", () => {
      mergeSandboxConfig({ apiKey: "from-global" });
      assert.equal(getApiKey("override"), "override");
    });

    it("uses merged apiKey", () => {
      mergeSandboxConfig({ apiKey: "k-global" });
      assert.equal(getApiKey(), "k-global");
    });

    it("falls back to LIGHTNING_API_KEY", () => {
      process.env.LIGHTNING_API_KEY = "k-env";
      assert.equal(getApiKey(), "k-env");
    });

    it("prefers LIGHTNING_SANDBOX_API_KEY over LIGHTNING_API_KEY", () => {
      process.env.LIGHTNING_API_KEY = "k-legacy";
      process.env.LIGHTNING_SANDBOX_API_KEY = "k-sandbox";
      try {
        assert.equal(getApiKey(), "k-sandbox");
      } finally {
        delete process.env.LIGHTNING_SANDBOX_API_KEY;
      }
    });
  });

  describe("getBaseUrl", () => {
    it("defaults to production origin", () => {
      assert.equal(getBaseUrl(), DEFAULT_LIGHTNING_BASE_URL);
    });

    it("uses merged baseUrl over env and default", () => {
      process.env.LIGHTNING_CLOUD_URL = "https://env.example";
      mergeSandboxConfig({ baseUrl: "https://merged.example" });
      assert.equal(getBaseUrl(), "https://merged.example");
    });

    it("uses LIGHTNING_CLOUD_URL when set", () => {
      process.env.LIGHTNING_CLOUD_URL = "https://staging.example";
      assert.equal(getBaseUrl(), "https://staging.example");
    });
  });

  describe("mergeSandboxConfig", () => {
    it("merges shallowly with previous patches", () => {
      mergeSandboxConfig({ apiKey: "a", baseUrl: "https://one" });
      mergeSandboxConfig({ baseUrl: "https://two" });
      assert.equal(getApiKey(), "a");
      assert.equal(getBaseUrl(), "https://two");
    });
  });
});
