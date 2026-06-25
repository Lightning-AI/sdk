/**
 * Unit tests for the PTY namespace. The Lightning controlplane attach
 * endpoint is a live WebSocket; here we fake the global `WebSocket`
 * constructor so we can exercise the SDK end-to-end (URL construction,
 * input/resize framing, lifecycle events) without a running server.
 */
import test from "node:test";
import assert from "node:assert/strict";

import { PtyHandle } from "../src/pty.js";
import { SandboxProcess } from "../src/process.js";
import type { CommandResult, RunCommandOpts } from "../src/types.js";

// ---------------------------------------------------------------------------
// Tiny WebSocket stand-in
// ---------------------------------------------------------------------------

interface FakeMessageEvent {
  data: unknown;
}
interface FakeCloseEvent {
  code: number;
  reason: string;
}

type Listener<E> = (ev: E) => void;

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];

  readonly url: string;
  readonly ctorOpts: { headers?: Record<string, string> } | undefined;
  binaryType: BinaryType = "blob";
  readonly sent: string[] = [];
  closed = false;
  closeCode?: number;
  closeReason?: string;

  private listeners: Record<string, Array<Listener<unknown>>> = {};

  constructor(url: string, opts?: { headers?: Record<string, string> }) {
    this.url = url;
    this.ctorOpts = opts;
    FakeWebSocket.instances.push(this);
  }

  addEventListener(name: string, fn: Listener<unknown>): void {
    (this.listeners[name] ??= []).push(fn);
  }

  send(data: string | ArrayBufferView | ArrayBuffer): void {
    this.sent.push(typeof data === "string" ? data : "<binary>");
  }

  close(code?: number, reason?: string): void {
    if (this.closed) return;
    this.closed = true;
    this.closeCode = code ?? 1000;
    this.closeReason = reason ?? "";
    queueMicrotask(() =>
      this.fire("close", { code: this.closeCode!, reason: this.closeReason! }),
    );
  }

  // -- helpers used by the test driver --

  fireOpen(): void {
    this.fire("open", {});
  }
  fireMessage(data: unknown): void {
    this.fire("message", { data } as FakeMessageEvent);
  }
  fireClose(code = 1000, reason = ""): void {
    this.closed = true;
    this.fire("close", { code, reason } as FakeCloseEvent);
  }

  private fire(name: string, ev: unknown): void {
    const list = this.listeners[name] ?? [];
    for (const fn of list) fn(ev);
  }
}

function installFakeWebSocket(): void {
  (globalThis as unknown as { WebSocket: typeof FakeWebSocket }).WebSocket = FakeWebSocket;
  FakeWebSocket.instances = [];
}

function uninstallFakeWebSocket(): void {
  delete (globalThis as unknown as { WebSocket?: unknown }).WebSocket;
}

// ---------------------------------------------------------------------------
// Tests for SandboxProcess (URL + auth + flows)
// ---------------------------------------------------------------------------

test("createPty builds the WebSocket URL the controlplane expects", async () => {
  installFakeWebSocket();
  try {
    const proc = new SandboxProcess({
      sandboxId: "sb-abc",
      organizationId: "org-1",
      clusterId: "cluster-1",
      getApiKey: () => "test-key",
      getBaseUrl: () => "https://lightning.test",
      runCommand: async () => ({ cmdId: "x", output: "", exitCode: 0 }),
    });

    const pty = await proc.createPty({
      sessionName: "shell",
      cols: 100,
      rows: 40,
    });
    assert.equal(FakeWebSocket.instances.length, 1);
    const ws = FakeWebSocket.instances[0];

    const url = new URL(ws.url);
    assert.equal(url.protocol, "wss:");
    assert.equal(url.host, "lightning.test");
    // The sandbox itself is the "machine" the controlplane attaches to.
    assert.equal(url.pathname, "/v1/clusters/cluster-1/machines/sb-abc/attach");
    assert.equal(url.searchParams.get("sessionName"), "shell");
    assert.equal(url.searchParams.get("cols"), "100");
    assert.equal(url.searchParams.get("rows"), "40");
    assert.equal(url.searchParams.get("restore"), null);

    assert.equal(ws.ctorOpts?.headers?.Authorization, "Bearer test-key");
    assert.equal(ws.ctorOpts?.headers?.["X-Lightning-Organization-Id"], "org-1");

    // Fully drain the handle so the test exits cleanly.
    ws.fireOpen();
    ws.fireClose(1000);
    await pty.wait();
  } finally {
    uninstallFakeWebSocket();
  }
});

test("connectPty sets restore=true so the server reattaches to the screen session", async () => {
  installFakeWebSocket();
  try {
    const proc = new SandboxProcess({
      sandboxId: "sb-abc",
      organizationId: "",
      clusterId: "cluster-1",
      getApiKey: () => "k",
      getBaseUrl: () => "http://localhost:9800",
      runCommand: async () => ({ cmdId: "x", output: "", exitCode: 0 }),
    });

    const pty = await proc.connectPty("shell");
    const ws = FakeWebSocket.instances[0];
    const url = new URL(ws.url);

    assert.equal(url.protocol, "ws:");
    assert.equal(url.pathname, "/v1/clusters/cluster-1/machines/sb-abc/attach");
    assert.equal(url.searchParams.get("sessionName"), "shell");
    assert.equal(url.searchParams.get("restore"), "true");

    ws.fireOpen();
    ws.fireClose(1000);
    await pty.wait();
  } finally {
    uninstallFakeWebSocket();
  }
});

test("listPtySessions parses screen -ls output", async () => {
  installFakeWebSocket();
  try {
    const screenOutput = [
      "There are screens on:",
      "        12345.shell    (Detached)",
      "        67890.build    (Attached)",
      "2 Sockets in /run/screen/S-root.",
      "",
    ].join("\n");

    const calls: RunCommandOpts[] = [];
    const proc = new SandboxProcess({
      sandboxId: "sb-abc",
      organizationId: "",
      clusterId: "cluster-1",
      getApiKey: () => "k",
      getBaseUrl: () => "http://localhost:9800",
      runCommand: async (opts) => {
        calls.push(opts);
        return {
          cmdId: "x",
          output: screenOutput,
          exitCode: 1, // `screen -ls` exits non-zero with sessions; we don't care
        } as CommandResult;
      },
    });

    const sessions = await proc.listPtySessions();
    assert.deepEqual(calls, [{ cmd: "screen", args: ["-ls"] }]);
    assert.equal(sessions.length, 2);
    assert.equal(sessions[0].id, "shell");
    assert.equal(sessions[0].active, false);
    assert.equal(sessions[0].processId, 12345);
    assert.equal(sessions[1].id, "build");
    assert.equal(sessions[1].active, true);
  } finally {
    uninstallFakeWebSocket();
  }
});

test("killPtySession runs `screen -X -S {sessionName} quit` and removes the local handle", async () => {
  installFakeWebSocket();
  try {
    const calls: RunCommandOpts[] = [];
    const proc = new SandboxProcess({
      sandboxId: "sb-abc",
      organizationId: "",
      clusterId: "cluster-1",
      getApiKey: () => "k",
      getBaseUrl: () => "http://localhost:9800",
      runCommand: async (opts) => {
        calls.push(opts);
        return { cmdId: "x", output: "", exitCode: 0 };
      },
    });

    const pty = await proc.createPty({
      sessionName: "doomed",
    });
    const ws = FakeWebSocket.instances[0];
    ws.fireOpen();

    await proc.killPtySession("doomed");
    // Should have sent Ctrl+C through the socket and then closed it.
    assert.equal(ws.sent.includes("\u0003"), true);
    assert.equal(ws.closed, true);

    // And it should have invoked screen -X to clean up the remote session.
    assert.equal(
      calls.some(
        (c) =>
          c.cmd === "screen" &&
          c.args?.[0] === "-X" &&
          c.args?.[1] === "-S" &&
          c.args?.[2] === "doomed" &&
          c.args?.[3] === "quit",
      ),
      true,
    );

    // Allow the close microtask to fire so wait() resolves.
    await pty.wait();
  } finally {
    uninstallFakeWebSocket();
  }
});

// ---------------------------------------------------------------------------
// Tests for PtyHandle directly
// ---------------------------------------------------------------------------

test("PtyHandle delivers shell output through onData and resolves wait() on clean close", async () => {
  installFakeWebSocket();
  try {
    const ws = new FakeWebSocket("wss://test/ignored");
    const chunks: string[] = [];

    const handle = new PtyHandle({
      id: "x",
      ws: ws as unknown as WebSocket,
      cols: 80,
      rows: 24,
      onData: (data) => chunks.push(new TextDecoder().decode(data)),
    });

    ws.fireOpen();
    await handle.waitForConnection();
    assert.equal(handle.isConnected(), true);

    ws.fireMessage("hello\n");
    ws.fireMessage("world\n");
    assert.deepEqual(chunks, ["hello\n", "world\n"]);

    // Clean close — exitCode should be 0, error should be null.
    ws.fireClose(1000);
    const result = await handle.wait();
    assert.equal(result.exitCode, 0);
    assert.equal(result.error, null);
    assert.equal(handle.isConnected(), false);
  } finally {
    uninstallFakeWebSocket();
  }
});

test("PtyHandle.sendInput forwards text frames; resize sends the JSON control frame", async () => {
  installFakeWebSocket();
  try {
    const ws = new FakeWebSocket("wss://test/ignored");
    const handle = new PtyHandle({
      id: "x",
      ws: ws as unknown as WebSocket,
      cols: 80,
      rows: 24,
    });

    ws.fireOpen();
    await handle.waitForConnection();

    await handle.sendInput("ls -la\n");
    await handle.sendInput(new Uint8Array([0x03])); // Ctrl+C, decoded as text
    await handle.resize(120, 30);

    assert.equal(ws.sent[0], "ls -la\n");
    assert.equal(ws.sent[1], "\u0003");
    assert.equal(ws.sent[2], JSON.stringify({ type: "resize", cols: 120, rows: 30 }));

    assert.deepEqual(handle.size, { cols: 120, rows: 30 });

    ws.fireClose(1000);
    await handle.wait();
  } finally {
    uninstallFakeWebSocket();
  }
});

test("PtyHandle reports abnormal close as exitCode=-1 with a populated error", async () => {
  installFakeWebSocket();
  try {
    const ws = new FakeWebSocket("wss://test/ignored");
    const handle = new PtyHandle({
      id: "x",
      ws: ws as unknown as WebSocket,
      cols: 80,
      rows: 24,
    });

    ws.fireOpen();
    await handle.waitForConnection();
    ws.fireClose(1006, "remote dropped");

    const result = await handle.wait();
    assert.equal(result.exitCode, -1);
    assert.equal(result.error, "remote dropped");
    assert.equal(handle.exitCode, -1);
    assert.equal(handle.error, "remote dropped");
  } finally {
    uninstallFakeWebSocket();
  }
});

test("PtyHandle flushes envs and cwd as initial input lines", async () => {
  installFakeWebSocket();
  try {
    const ws = new FakeWebSocket("wss://test/ignored");
    const handle = new PtyHandle({
      id: "x",
      ws: ws as unknown as WebSocket,
      cols: 80,
      rows: 24,
      initialInput: ["export FOO='bar baz'\n", "cd '/work dir' && clear\n"],
    });

    ws.fireOpen();
    await handle.waitForConnection();

    assert.equal(ws.sent[0], "export FOO='bar baz'\n");
    assert.equal(ws.sent[1], "cd '/work dir' && clear\n");

    ws.fireClose(1000);
    await handle.wait();
  } finally {
    uninstallFakeWebSocket();
  }
});
