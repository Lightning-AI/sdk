import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, it } from "node:test";
import { resetSandboxConfig } from "../src/config.js";
import { Sandbox } from "../src/sandbox.js";
import { jsonResponse } from "./helpers.js";
import type { V1Sandbox } from "../src/lightning_cloud/openapi/data-contracts.js";

describe("FileSystem", () => {
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

  async function runningSandbox(): Promise<Sandbox> {
    enqueueJson(sampleV1({ status: "running" }));
    return Sandbox.create({ name: "x", instanceType: "cpu-1" });
  }

  /** Single command run: capture POST /commands body and return a fixed command response. */
  function mockOneCommand(output: string, exitCode: number): {
    command: string;
    args: string[];
  } {
    const cap = { command: "", args: [] as string[] };
    globalThis.fetch = ((_input, init) => {
      const body = init?.body ? JSON.parse(String(init.body)) : {};
      cap.command = (body as { command: string }).command;
      cap.args = (body as { args?: string[] }).args ?? [];
      return Promise.resolve(jsonResponse({ cmdId: "c", output, exitCode }));
    }) as typeof fetch;
    return cap;
  }

  it("writeFile (path, content) POSTs to files API", async () => {
    const sb = await runningSandbox();
    let posted: unknown;
    globalThis.fetch = ((input, init) => {
      assert.ok(String(input).includes("/files"));
      assert.ok(!String(input).includes("/commands"));
      assert.equal(init?.method, "POST");
      posted = JSON.parse(String(init?.body));
      return Promise.resolve(jsonResponse({}));
    }) as typeof fetch;
    await sb.fs.writeFile("/x/a.txt", "hello");
    assert.deepEqual(posted, {
      organizationId: "org-1",
      path: "/x/a.txt",
      content: "hello",
    });
  });

  it("writeFile ({ path, content }) POSTs same shape", async () => {
    const sb = await runningSandbox();
    let posted: unknown;
    globalThis.fetch = ((_input, init) => {
      posted = JSON.parse(String(init?.body));
      return Promise.resolve(jsonResponse({}));
    }) as typeof fetch;
    await sb.fs.writeFile({ path: "/y/b.txt", content: "yo" });
    assert.deepEqual(posted, {
      organizationId: "org-1",
      path: "/y/b.txt",
      content: "yo",
    });
  });

  it("exists uses test -e and returns true on exit 0", async () => {
    const sb = await runningSandbox();
    const cap = mockOneCommand("", 0);
    assert.equal(await sb.fs.exists("/tmp/x"), true);
    assert.equal(cap.command, "test");
    assert.deepEqual(cap.args, ["-e", "/tmp/x"]);
  });

  it("exists returns false when exitCode is non-zero", async () => {
    const sb = await runningSandbox();
    mockOneCommand("", 1);
    assert.equal(await sb.fs.exists("/missing"), false);
  });

  it("stat parses stat --format output", async () => {
    const sb = await runningSandbox();
    const cap = mockOneCommand("regular file|1024|1715000000|644\n", 0);
    const st = await sb.fs.stat("/a/b");
    assert.equal(cap.command, "stat");
    assert.deepEqual(cap.args, ["--format=%F|%s|%Y|%a", "/a/b"]);
    assert.equal(st.fileType, "regular file");
    assert.equal(st.size, 1024);
    assert.equal(st.mode, "644");
    assert.equal(st.mtime.getTime(), 1715000000 * 1000);
  });

  it("stat throws when command fails", async () => {
    const sb = await runningSandbox();
    mockOneCommand("stat: cannot stat\n", 1);
    await assert.rejects(() => sb.fs.stat("/nope"), /stat \/nope failed \(exit 1\)/);
  });

  it("stat throws on unexpected output shape", async () => {
    const sb = await runningSandbox();
    mockOneCommand("not-enough-fields\n", 0);
    await assert.rejects(() => sb.fs.stat("/x"), /unexpected stat output for \/x/);
  });

  it("readdir uses ls -1A and splits lines", async () => {
    const sb = await runningSandbox();
    const cap = mockOneCommand(".hidden\na\nb\n\n", 0);
    const names = await sb.fs.readdir("/dir");
    assert.equal(cap.command, "ls");
    assert.deepEqual(cap.args, ["-1A", "/dir"]);
    assert.deepEqual(names, [".hidden", "a", "b"]);
  });

  it("readdir throws when ls fails", async () => {
    const sb = await runningSandbox();
    mockOneCommand("ls: cannot access\n", 2);
    await assert.rejects(() => sb.fs.readdir("/bad"), /readdir \/bad failed \(exit 2\)/);
  });

  it("rm runs rm with path only", async () => {
    const sb = await runningSandbox();
    const cap = mockOneCommand("", 0);
    await sb.fs.rm("/x/a");
    assert.equal(cap.command, "rm");
    assert.deepEqual(cap.args, ["/x/a"]);
  });

  it("rm with recursive uses rm -rf", async () => {
    const sb = await runningSandbox();
    const cap = mockOneCommand("", 0);
    await sb.fs.rm("/tree", { recursive: true });
    assert.equal(cap.command, "rm");
    assert.deepEqual(cap.args, ["-rf", "/tree"]);
  });

  it("rm throws on failure", async () => {
    const sb = await runningSandbox();
    mockOneCommand("rm: cannot remove\n", 1);
    await assert.rejects(() => sb.fs.rm("/read-only"), /rm \/read-only failed \(exit 1\)/);
  });

  it("rename runs mv", async () => {
    const sb = await runningSandbox();
    const cap = mockOneCommand("", 0);
    await sb.fs.rename("/old", "/new");
    assert.equal(cap.command, "mv");
    assert.deepEqual(cap.args, ["/old", "/new"]);
  });

  it("copyFile runs cp", async () => {
    const sb = await runningSandbox();
    const cap = mockOneCommand("", 0);
    await sb.fs.copyFile("/src", "/dst");
    assert.equal(cap.command, "cp");
    assert.deepEqual(cap.args, ["/src", "/dst"]);
  });

  it("chmod passes octal string for numeric mode", async () => {
    const sb = await runningSandbox();
    const cap = mockOneCommand("", 0);
    await sb.fs.chmod("/f", 0o755);
    assert.equal(cap.command, "chmod");
    assert.deepEqual(cap.args, ["755", "/f"]);
  });

  it("chmod passes string mode through", async () => {
    const sb = await runningSandbox();
    const cap = mockOneCommand("", 0);
    await sb.fs.chmod("/f", "644");
    assert.deepEqual(cap.args, ["644", "/f"]);
  });

  it("symlink runs ln -s", async () => {
    const sb = await runningSandbox();
    const cap = mockOneCommand("", 0);
    await sb.fs.symlink("/target", "/link");
    assert.equal(cap.command, "ln");
    assert.deepEqual(cap.args, ["-s", "/target", "/link"]);
  });
});
