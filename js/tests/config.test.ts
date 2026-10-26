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

    it("refuses a legacy UUID in LIGHTNING_API_KEY with the migration message", () => {
      process.env.LIGHTNING_API_KEY = "3f2b8c1e-9d4a-4b7f-8e21-0a6c5d9f7b10";
      assert.throws(() => getApiKey(), /no longer supported/);
    });

    it("refuses an sk-lit- key in LIGHTNING_API_KEY with the migration message", () => {
      process.env.LIGHTNING_API_KEY = "sk-lit-0123456789abcdef";
      assert.throws(() => getApiKey(), /no longer supported/);
    });

    it("does not read LIGHTNING_API_KEY when an explicit key is given", () => {
      process.env.LIGHTNING_API_KEY = "sk-lit-0123456789abcdef";
      assert.equal(getApiKey("override"), "override");
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
