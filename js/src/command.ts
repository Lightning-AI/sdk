import type { Sandbox } from "./sandbox.js";
import type { CommandLog, CommandStatus, WaitForCommandOptions } from "./types.js";

/**
 * Handle for a command running (or finished) inside a sandbox.
 *
 * - When {@link Sandbox.runCommand} is awaited *without* `detached: true`, the
 *   server has already waited for the process to exit, so `exitCode` is a
 *   number and `running` is `false` immediately.
 * - When `detached: true` is passed, the call returns immediately with
 *   `exitCode === null` and `running === true`. Call {@link wait} to block
 *   until the process exits, or {@link kill} to terminate it.
 *
 * ```ts
 * const detachedCmd = await sandbox.runCommand({
 *   cmd: "sleep",
 *   args: ["5"],
 *   detached: true,
 * });
 * const result = await detachedCmd.wait();
 * if (result.exitCode !== 0) {
 *   console.error("Something went wrong...");
 * }
 * ```
 */
export class Command {
  readonly cmdId: string;
  /** Captured combined stdout/stderr seen so far. Updated by {@link wait} and {@link getStatus}. */
  output: string;
  /** Exit code; `null` while the command is still running. */
  exitCode: number | null;
  /**
   * The command line as recorded by the server. Only populated on handles
   * returned by {@link Sandbox.listCommands}; `""` otherwise.
   */
  readonly command: string;
  /**
   * Server-side creation timestamp. Only populated on handles returned by
   * {@link Sandbox.listCommands}; `null` on handles from `runCommand`.
   */
  readonly startedAt: string | null;
  /**
   * Server-side update timestamp. Only populated on handles returned by
   * {@link Sandbox.listCommands}; `null` on handles from `runCommand`.
   */
  readonly updatedAt: string | null;

  protected readonly sandbox: Sandbox;

  constructor(
    sandbox: Sandbox,
    data: {
      cmdId: string;
      output: string;
      exitCode: number | null;
      command?: string;
      startedAt?: string | null;
      updatedAt?: string | null;
    },
  ) {
    this.sandbox = sandbox;
    this.cmdId = data.cmdId;
    this.output = data.output;
    this.exitCode = data.exitCode;
    this.command = data.command ?? "";
    this.startedAt = data.startedAt ?? null;
    this.updatedAt = data.updatedAt ?? null;
  }

  /** `true` while the command is still executing (i.e. {@link exitCode} is `null`). */
  get running(): boolean {
    return this.exitCode === null;
  }

  /** Returns the captured combined stdout/stderr buffered on the handle. */
  stdout(): string {
    return this.output;
  }

  /** Alias for {@link stdout}; the API exposes a single combined output stream. */
  stderr(): string {
    return this.output;
  }

  /**
   * Fetch this command's log lines from the server.
   *
   * Returns the timestamped log messages via {@link Sandbox.getCommandLogs}.
   * Unlike {@link stdout} (a single combined buffer), this returns discrete
   * `{ timestamp, message }` entries.
   */
  async logs(): Promise<CommandLog[]> {
    const { logs } = await this.sandbox.getCommandLogs(this.cmdId);
    return logs;
  }

  /**
   * Refresh status from the server, updating {@link output} and {@link exitCode}.
   *
   * The returned {@link CommandStatus} is the raw server response and is also
   * useful for inspecting `running` directly.
   */
  async getStatus(): Promise<CommandStatus> {
    const status = await this.sandbox.getCommand(this.cmdId);
    this.output = status.output;
    if (!status.running) {
      this.exitCode = status.exitCode;
    }
    return status;
  }

  /**
   * Block until the command exits, then return this handle with `exitCode`
   * populated. Essential for detached commands where you need to know when
   * execution completes; for non-detached commands, {@link Sandbox.runCommand}
   * already waits automatically and `wait()` returns immediately.
   *
   * Resolves immediately if the command has already exited. Otherwise polls
   * {@link Sandbox.getCommand} until `running` becomes `false`.
   */
  async wait(opts: WaitForCommandOptions = {}): Promise<Command> {
    if (this.exitCode !== null) {
      return this;
    }
    const final = await this.sandbox.waitForCommand(this.cmdId, opts);
    this.output = final.output;
    this.exitCode = final.exitCode;
    return this;
  }

  /** Terminate the command (best effort) via {@link Sandbox.killCommand}. */
  async kill(): Promise<void> {
    await this.sandbox.killCommand(this.cmdId);
  }
}
