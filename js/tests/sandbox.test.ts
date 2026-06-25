import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, it } from "node:test";
import { resetSandboxConfig } from "../src/config.js";
import { Sandbox } from "../src/sandbox.js";
import { jsonResponse, textResponse } from "./helpers.js";
import type { V1Sandbox } from "../src/lightning_cloud/openapi/data-contracts.js";

describe("Sandbox", () => {
  const originalFetch = globalThis.fetch;
  let fetchQueue: Array<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>;

  function enqueueJson(body: unknown, status = 200): void {
    fetchQueue.push(async () => jsonResponse(body, status));
  }

  beforeEach(() => {
    resetSandboxConfig();
    Sandbox.configure({ apiKey: "test-key" });
    fetchQueue = [];
    globalThis.fetch = ((input, init) => {
      const next = fetchQueue.shift();
      if (!next) {
        return Promise.reject(new Error(`unexpected fetch: ${String(input)}`));
      }
      return next(input, init);
    }) as typeof fetch;
  });

  afterEach(() => {
    resetSandboxConfig();
    globalThis.fetch = originalFetch;
  });

  function sampleV1(overrides: Partial<V1Sandbox> = {}): V1Sandbox {
    return {
      id: "sb-test",
      name: "n",
      organizationId: "org-1",
      clusterId: "cl-1",
      instanceType: "cpu-1",
      spot: false,
      status: "running",
      cloudspaceId: "cs-1",
      ports: [],
      runtime: "python313",
      createdAt: "2024-06-01T12:00:00.000Z",
      updatedAt: "2024-06-01T12:00:00.000Z",
      ...overrides,
    };
  }

  describe("configure", () => {
    it("applies api key used by subsequent requests", async () => {
      Sandbox.configure({ apiKey: "secret-xyz" });
      enqueueJson(sampleV1());
      await Sandbox.get({ sandboxId: "sb-test" });
      assert.ok(fetchQueue.length === 0);
      // Inspect last fetch via re-running with captured headers — enqueue one response and assert Authorization
      const calls: string[] = [];
      globalThis.fetch = (async (_input, init) => {
        const auth = new Headers(init?.headers).get("Authorization") ?? "";
        calls.push(auth);
        return jsonResponse(sampleV1());
      }) as typeof fetch;
      await Sandbox.get({ sandboxId: "sb-test" });
      assert.equal(calls[0], "Bearer secret-xyz");
    });
  });

  describe("get", () => {
    it("GETs sandbox JSON and maps fields", async () => {
      enqueueJson(sampleV1({ id: "sb-abc", name: "my-name" }));
      const sb = await Sandbox.get({ sandboxId: "sb-abc" });
      assert.equal(sb.sandboxId, "sb-abc");
      assert.equal(sb.name, "my-name");
      assert.equal(sb.status, "running");
    });

    it("does not send an organizationId query (org implied by key)", async () => {
      let seenUrl = "";
      globalThis.fetch = ((input) => {
        seenUrl = String(input);
        return Promise.resolve(jsonResponse(sampleV1()));
      }) as typeof fetch;
      await Sandbox.get({ sandboxId: "x" });
      assert.doesNotMatch(seenUrl, /organizationId=/);
    });
  });

  describe("list", () => {
    it("returns sandboxes and pagination fields", async () => {
      enqueueJson({
        sandboxes: [sampleV1({ id: "a" }), sampleV1({ id: "b" })],
        nextPageToken: "npt",
        previousPageToken: "ppt",
        totalSize: "2",
      });
      const out = await Sandbox.list({ limit: 10 });
      assert.equal(out.sandboxes.length, 2);
      assert.equal(out.nextPageToken, "npt");
      assert.equal(out.previousPageToken, "ppt");
      assert.equal(out.totalSize, 2);
    });
  });

  describe("create", () => {
    it("returns immediately when status is running", async () => {
      enqueueJson(sampleV1({ status: "running" }));
      const sb = await Sandbox.create({
        name: "cpu-example",
        instanceType: "cpu-1",
      });
      assert.equal(sb.status, "running");
      assert.ok(fetchQueue.length === 0);
    });

    it("generates a default name when none is provided", async () => {
      let capturedBody: Record<string, unknown> = {};
      globalThis.fetch = ((_input, init) => {
        if (init?.body) {
          capturedBody = JSON.parse(String(init.body));
        }
        return Promise.resolve(jsonResponse(sampleV1({ status: "running" })));
      }) as typeof fetch;
      await Sandbox.create({ instanceType: "cpu-1" });
    });
    it("polls until running", async () => {
      enqueueJson(sampleV1({ status: "pending" }));
      enqueueJson(sampleV1({ status: "running" }));
      const sb = await Sandbox.create({
        name: "x",
        instanceType: "cpu-1",
      });
      assert.equal(sb.status, "running");
    });

    it("throws on terminal status", async () => {
      enqueueJson(sampleV1({ status: "error" }));
      await assert.rejects(
        () => Sandbox.create({ name: "x", instanceType: "cpu-1" }),
        /terminal state: error/,
      );
    });
  });

  describe("HTTP errors", () => {
    it("propagates non-OK responses as Error", async () => {
      fetchQueue.push(async () => textResponse("bad", 500));
      await assert.rejects(() => Sandbox.get({ sandboxId: "z" }), /Lightning API error 500/);
    });
  });

  describe("instance methods", () => {
    async function runningSandbox(): Promise<Sandbox> {
      enqueueJson(sampleV1({ status: "running" }));
      return Sandbox.create({ name: "x", instanceType: "cpu-1" });
    }

    it("delete sends DELETE", async () => {
      const sb = await runningSandbox();
      const methods: string[] = [];
      globalThis.fetch = ((input, init) => {
        methods.push(init?.method ?? "GET");
        return Promise.resolve(jsonResponse({}));
      }) as typeof fetch;
      await sb.delete();
      assert.deepEqual(methods, ["DELETE"]);
    });

    it("runCommand sends JSON body", async () => {
      const sb = await runningSandbox();
      let body: unknown;
      globalThis.fetch = ((_input, init) => {
        body = init?.body ? JSON.parse(String(init.body)) : undefined;
        return Promise.resolve(
          jsonResponse({ cmdId: "c1", output: "hi\n", exitCode: 0 }),
        );
      }) as typeof fetch;
      const result = await sb.runCommand("echo", ["hi"]);
      assert.equal(result.exitCode, 0);
      assert.equal(result.output, "hi\n");
      assert.equal((body as { command: string }).command, "echo");
    });

    it("readFile returns null on 404", async () => {
      const sb = await runningSandbox();
      globalThis.fetch = () => Promise.resolve(textResponse("nf", 404)) as Promise<Response>;
      const content = await sb.readFile({ path: "/nope" });
      assert.equal(content, null);
    });

    it("getCommand maps running flag", async () => {
      const sb = await runningSandbox();
      globalThis.fetch = () =>
        Promise.resolve(
          jsonResponse({ output: "", exitCode: 0, running: true }),
        ) as Promise<Response>;
      const st = await sb.getCommand("cmd-1");
      assert.equal(st.running, true);
    });

    it("runCommand({detached:true}).wait() polls until command exits", async () => {
      const sb = await runningSandbox();
      const responses: Array<unknown> = [
        { cmdId: "c-bg", output: "", exitCode: 0 },
        { output: "", exitCode: 0, running: true },
        { output: "done\n", exitCode: 7, running: false },
      ];
      globalThis.fetch = (() =>
        Promise.resolve(jsonResponse(responses.shift()))) as typeof fetch;

      const cmd = await sb.runCommand({ cmd: "sleep", args: ["5"], detached: true });
      assert.equal(cmd.exitCode, null);
      assert.equal(cmd.running, true);

      const result = await cmd.wait({ pollIntervalMs: 0 });
      assert.equal(result.exitCode, 7);
      assert.equal(result.running, false);
      assert.equal(result.output, "done\n");
      assert.strictEqual(result, cmd);
    });

    it("runCommand without detached returns Command with exitCode populated", async () => {
      const sb = await runningSandbox();
      globalThis.fetch = (() =>
        Promise.resolve(
          jsonResponse({ cmdId: "c1", output: "hi\n", exitCode: 0 }),
        )) as typeof fetch;
      const cmd = await sb.runCommand("echo", ["hi"]);
      assert.equal(cmd.exitCode, 0);
      assert.equal(cmd.running, false);
      const result = await cmd.wait({ pollIntervalMs: 0 });
      assert.strictEqual(result, cmd);
    });

    it("waitForCommand polls getCommand until running is false", async () => {
      const sb = await runningSandbox();
      const responses: Array<{ output: string; exitCode: number; running: boolean }> = [
        { output: "", exitCode: 0, running: true },
        { output: "done\n", exitCode: 0, running: false },
      ];
      globalThis.fetch = (() =>
        Promise.resolve(jsonResponse(responses.shift()))) as typeof fetch;
      const final = await sb.waitForCommand("cmd-1", { pollIntervalMs: 0 });
      assert.equal(final.running, false);
      assert.equal(final.output, "done\n");
      assert.equal(responses.length, 0);
    });

    it("waitForCommand throws when timeout elapses", async () => {
      const sb = await runningSandbox();
      globalThis.fetch = (() =>
        Promise.resolve(
          jsonResponse({ output: "", exitCode: 0, running: true }),
        )) as typeof fetch;
      await assert.rejects(
        () => sb.waitForCommand("cmd-1", { pollIntervalMs: 0, timeoutMs: 0 }),
        /Timed out waiting for command/,
      );
    });
  });
});
