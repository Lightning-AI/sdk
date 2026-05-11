import type { Sandbox } from "./sandbox.js";
import type { Command } from "./command.js";
import type { FileStat, WriteFileParams } from "./types.js";

function assertCommandOk(r: Command, what: string): void {
  if (r.exitCode === 0) return;
  const tail = r.output.trim();
  throw new Error(`${what} failed (exit ${r.exitCode})${tail ? `: ${tail}` : ""}`);
}

export class FileSystem {
  constructor(private readonly sandbox: Sandbox) {}

  async writeFile(path: string, content: string): Promise<void>;
  async writeFile(params: WriteFileParams): Promise<void>;
  async writeFile(pathOrParams: string | WriteFileParams, content?: string): Promise<void> {
    const params =
      typeof pathOrParams === "string"
        ? { path: pathOrParams, content: content ?? "" }
        : pathOrParams;
    return this.sandbox.writeFile(params);
  }

  async exists(path: string): Promise<boolean> {
    const r = await this.sandbox.runCommand("test", ["-e", path]);
    return r.exitCode === 0;
  }

  async stat(path: string): Promise<FileStat> {
    const r = await this.sandbox.runCommand("stat", ["--format=%F|%s|%Y|%a", path]);
    assertCommandOk(r, `stat ${path}`);
    const line = r.output.trim();
    const parts = line.split("|");
    if (parts.length < 4) {
      throw new Error(`unexpected stat output for ${path}: ${line}`);
    }
    const [fileType, sizeStr, mtimeSecStr, mode] = parts;
    return {
      fileType,
      size: Number(sizeStr),
      mtime: new Date(Number(mtimeSecStr) * 1000),
      mode,
    };
  }

  async readdir(path: string): Promise<string[]> {
    const r = await this.sandbox.runCommand("ls", ["-1A", path]);
    assertCommandOk(r, `readdir ${path}`);
    return r.output.split("\n").filter(Boolean);
  }

  async rm(path: string, opts?: { recursive?: boolean }): Promise<void> {
    const args = opts?.recursive ? ["-rf", path] : [path];
    const r = await this.sandbox.runCommand("rm", args);
    assertCommandOk(r, `rm ${path}`);
  }

  async rename(oldPath: string, newPath: string): Promise<void> {
    const r = await this.sandbox.runCommand("mv", [oldPath, newPath]);
    assertCommandOk(r, `rename ${oldPath} -> ${newPath}`);
  }

  async copyFile(src: string, dest: string): Promise<void> {
    const r = await this.sandbox.runCommand("cp", [src, dest]);
    assertCommandOk(r, `copyFile ${src} -> ${dest}`);
  }

  async chmod(path: string, mode: string | number): Promise<void> {
    const m = typeof mode === "number" ? mode.toString(8) : mode;
    const r = await this.sandbox.runCommand("chmod", [m, path]);
    assertCommandOk(r, `chmod ${path}`);
  }

  async symlink(target: string, path: string): Promise<void> {
    const r = await this.sandbox.runCommand("ln", ["-s", target, path]);
    assertCommandOk(r, `symlink ${path}`);
  }
}
