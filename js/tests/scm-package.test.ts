import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, it } from "node:test";
import { createPackage } from "../scripts/scm-package.mjs";

const temporaryDirectories: string[] = [];

function temporaryDirectory(prefix: string): string {
  const directory = mkdtempSync(join(tmpdir(), prefix));
  temporaryDirectories.push(directory);
  return directory;
}

function git(repository: string, ...args: string[]): void {
  execFileSync("git", args, { cwd: repository, stdio: "ignore" });
}

function taggedProject(): { projectRoot: string; repositoryRoot: string; sourceManifest: string } {
  const repositoryRoot = temporaryDirectory("lightning-sdk-package-test-");
  const projectRoot = join(repositoryRoot, "js");
  mkdirSync(join(projectRoot, "dist"), { recursive: true });
  const sourceManifest = `${JSON.stringify(
    {
      name: "@lightningai/sdk",
      version: "0.0.0",
      type: "module",
      main: "dist/index.js",
      files: ["dist"],
    },
    null,
    2,
  )}\n`;
  writeFileSync(join(projectRoot, "package.json"), sourceManifest);
  writeFileSync(join(projectRoot, "README.md"), "# Test package\n");
  writeFileSync(join(projectRoot, "dist", "index.js"), "export const ready = true;\n");

  git(repositoryRoot, "init", "--quiet");
  git(repositoryRoot, "config", "user.email", "tests@example.invalid");
  git(repositoryRoot, "config", "user.name", "SDK Tests");
  git(repositoryRoot, "add", ".");
  git(repositoryRoot, "commit", "--quiet", "-m", "initial package");
  git(repositoryRoot, "tag", "v2026.07.09.post0");

  return { projectRoot, repositoryRoot, sourceManifest };
}

afterEach(() => {
  for (const directory of temporaryDirectories.splice(0)) {
    rmSync(directory, { recursive: true, force: true });
  }
});

describe("SCM package creation", () => {
  it("packs an exact tag without modifying the source manifest", () => {
    const { projectRoot, repositoryRoot, sourceManifest } = taggedProject();
    const outputDirectory = temporaryDirectory("lightning-sdk-package-output-");

    const result = createPackage({ projectRoot, repositoryRoot, outputDirectory, releaseOnly: true });

    assert.equal(result.version, "2026.7.9-post0");
    assert.equal(readFileSync(join(projectRoot, "package.json"), "utf8"), sourceManifest);
    assert.ok(existsSync(result.tarballPath));
    const packedManifest = JSON.parse(
      execFileSync("tar", ["-xOf", result.tarballPath, "package/package.json"], { encoding: "utf8" }),
    );
    assert.equal(packedManifest.version, "2026.7.9-post0");
  });

  it("rejects a release build ahead of its tag", () => {
    const { projectRoot, repositoryRoot } = taggedProject();
    writeFileSync(join(projectRoot, "README.md"), "# Changed package\n");
    git(repositoryRoot, "add", ".");
    git(repositoryRoot, "commit", "--quiet", "-m", "change package");

    assert.throws(
      () =>
        createPackage({
          projectRoot,
          repositoryRoot,
          outputDirectory: temporaryDirectory("lightning-sdk-package-output-"),
          releaseOnly: true,
        }),
      /exactly at the version tag/,
    );
  });

  it("rejects a release build from a dirty worktree", () => {
    const { projectRoot, repositoryRoot } = taggedProject();
    writeFileSync(join(projectRoot, "README.md"), "# Dirty package\n");

    assert.throws(
      () =>
        createPackage({
          projectRoot,
          repositoryRoot,
          outputDirectory: temporaryDirectory("lightning-sdk-package-output-"),
          releaseOnly: true,
        }),
      /clean worktree/,
    );
  });
});
