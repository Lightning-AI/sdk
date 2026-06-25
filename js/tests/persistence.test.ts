import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, it } from "node:test";
import { resetSandboxConfig } from "../src/config.js";
import { Sandbox } from "../src/sandbox.js";
import { jsonResponse } from "./helpers.js";
import type {
  V1Sandbox,
  V1SandboxSnapshot,
} from "../src/lightning_cloud/openapi/data-contracts.js";

describe("Sandbox persistence & snapshots", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    resetSandboxConfig();
    Sandbox.configure({ apiKey: "test-key" });
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
      persistent: true,
      projectId: "proj-1",
      createdAt: "2024-06-01T12:00:00.000Z",
      updatedAt: "2024-06-01T12:00:00.000Z",
      ...overrides,
    };
  }

  function sampleSnapshot(overrides: Partial<V1SandboxSnapshot> = {}): V1SandboxSnapshot {
    return {
      id: "snap-1",
      organizationId: "org-1",
      projectId: "proj-1",
      sourceSandboxId: "sb-test",
      status: "ready",
      sizeBytes: "1024",
      createdAt: "2024-06-01T12:00:00.000Z",
      updatedAt: "2024-06-01T12:00:00.000Z",
      expiresAt: "",
      runtime: "python313",
      ...overrides,
    };
  }

  async function runningSandbox(): Promise<Sandbox> {
    globalThis.fetch = (() =>
      Promise.resolve(jsonResponse(sampleV1({ status: "running" })))) as typeof fetch;
    return Sandbox.create({ name: "x", instanceType: "cpu-1" });
  }

  it("create forwards persistent / snapshotId / timeout", async () => {
    let body: Record<string, unknown> = {};
    globalThis.fetch = ((_input, init) => {
      if (init?.body) body = JSON.parse(String(init.body));
      return Promise.resolve(jsonResponse(sampleV1({ status: "running" })));
    }) as typeof fetch;
    const sb = await Sandbox.create({
      name: "x",
      instanceType: "cpu-1",
      persistent: true,
      snapshotId: "snap-1",
      timeout: 60_000,
    });
    assert.equal(body.persistent, true);
    assert.equal(body.snapshotId, "snap-1");
    assert.equal(body.timeout, "60000");
    assert.equal(sb.persistent, true);
    assert.equal(sb.projectId, "proj-1"); // read back from the response
  });

  it("create omits persistent when not specified (server default applies)", async () => {
    let body: Record<string, unknown> = {};
    globalThis.fetch = ((_input, init) => {
      if (init?.body) body = JSON.parse(String(init.body));
      return Promise.resolve(jsonResponse(sampleV1({ status: "running" })));
    }) as typeof fetch;
    await Sandbox.create({ name: "x", instanceType: "cpu-1" });
    assert.equal("persistent" in body, false);
  });

  it("stop POSTs and returns autoSnapshotId", async () => {
    const sb = await runningSandbox();
    let url = "";
    let method = "";
    globalThis.fetch = ((input, init) => {
      url = String(input);
      method = init?.method ?? "GET";
      return Promise.resolve(jsonResponse({ autoSnapshotId: "snap-auto" }));
    }) as typeof fetch;
    const out = await sb.stop();
    assert.equal(method, "POST");
    assert.match(url, /\/v1\/core\/sandboxes\/sb-test\/stop/);
    assert.equal(out.autoSnapshotId, "snap-auto");
  });

  it("resume PATCHes resume:true and polls to running", async () => {
    const bodies: Record<string, unknown>[] = [];
    const methods: string[] = [];
    const responses: V1Sandbox[] = [
      sampleV1({ status: "pending" }), // PATCH response
      sampleV1({ status: "running" }), // GET poll
    ];
    globalThis.fetch = ((_input, init) => {
      methods.push(init?.method ?? "GET");
      if (init?.body) bodies.push(JSON.parse(String(init.body)));
      return Promise.resolve(jsonResponse(responses.shift()));
    }) as typeof fetch;
    const sb = await Sandbox.resume({ sandboxId: "sb-test" });
    assert.equal(methods[0], "PATCH");
    assert.equal(bodies[0].resume, true);
    assert.equal(sb.status, "running");
  });

  it("createSnapshot POSTs to /{id}/snapshot and maps the row", async () => {
    const sb = await runningSandbox();
    let url = "";
    let body: Record<string, unknown> = {};
    globalThis.fetch = ((input, init) => {
      url = String(input);
      if (init?.body) body = JSON.parse(String(init.body));
      return Promise.resolve(jsonResponse(sampleSnapshot({ status: "saving" })));
    }) as typeof fetch;
    const snap = await sb.createSnapshot({ excludes: ["node_modules"], wait: false });
    assert.match(url, /\/v1\/core\/sandboxes\/sb-test\/snapshot/);
    assert.deepEqual(body.excludes, ["node_modules"]);
    assert.equal(body.projectId, "proj-1"); // falls back to sandbox projectId
    assert.equal(snap.id, "snap-1");
    assert.equal(snap.sizeBytes, 1024);
  });

  it("listSnapshots returns mapped snapshots + pagination", async () => {
    globalThis.fetch = (() =>
      Promise.resolve(
        jsonResponse({
          snapshots: [sampleSnapshot({ id: "a" }), sampleSnapshot({ id: "b" })],
          nextPageToken: "npt",
          totalSize: "2",
        }),
      )) as typeof fetch;
    const out = await Sandbox.listSnapshots({ limit: 10 });
    assert.equal(out.snapshots.length, 2);
    assert.equal(out.snapshots[0].id, "a");
    assert.equal(out.nextPageToken, "npt");
    assert.equal(out.totalSize, 2);
  });

  it("deleteSnapshot sends DELETE to the snapshot path", async () => {
    let url = "";
    let method = "";
    globalThis.fetch = ((input, init) => {
      url = String(input);
      method = init?.method ?? "GET";
      return Promise.resolve(jsonResponse({}));
    }) as typeof fetch;
    await Sandbox.deleteSnapshot("snap-1");
    assert.equal(method, "DELETE");
    assert.match(url, /\/v1\/core\/sandboxes\/snapshots\/snap-1/);
  });
});
