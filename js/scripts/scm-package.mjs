import { execFileSync } from "node:child_process";
import { copyFileSync, cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { assertRelease, describeRepository, renderVersion } from "./scm-version.mjs";

function readManifest(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    throw new Error(`unable to read package manifest at ${path}: ${error.message}`);
  }
}

export function createPackage({
  projectRoot = process.cwd(),
  repositoryRoot = resolve(projectRoot, ".."),
  outputDirectory = join(projectRoot, "package"),
  releaseOnly = false,
} = {}) {
  const description = describeRepository(repositoryRoot);
  if (releaseOnly) {
    assertRelease(description);
  }
  const version = renderVersion(description);
  const sourceManifestPath = join(projectRoot, "package.json");
  const sourceManifest = readManifest(sourceManifestPath);
  const distributionDirectory = join(projectRoot, "dist");
  if (!existsSync(distributionDirectory)) {
    throw new Error(`package build output does not exist: ${distributionDirectory}`);
  }

  const stageRoot = mkdtempSync(join(tmpdir(), "lightning-sdk-npm-stage-"));
  try {
    const stagePackage = join(stageRoot, "package");
    mkdirSync(stagePackage);
    cpSync(distributionDirectory, join(stagePackage, "dist"), { recursive: true });
    const readmePath = join(projectRoot, "README.md");
    if (existsSync(readmePath)) {
      copyFileSync(readmePath, join(stagePackage, "README.md"));
    }
    writeFileSync(join(stagePackage, "package.json"), `${JSON.stringify({ ...sourceManifest, version }, null, 2)}\n`);

    mkdirSync(outputDirectory, { recursive: true });
    const packed = JSON.parse(
      execFileSync(
        "npm",
        ["pack", stagePackage, "--pack-destination", outputDirectory, "--json", "--ignore-scripts"],
        { encoding: "utf8" },
      ),
    );
    const result = packed[0];
    if (!result || result.version !== version || typeof result.filename !== "string") {
      throw new Error(`npm pack returned unexpected metadata for version ${version}`);
    }

    return {
      version,
      tarballPath: resolve(outputDirectory, basename(result.filename)),
      description,
    };
  } finally {
    rmSync(stageRoot, { recursive: true, force: true });
  }
}

function parseArguments(args) {
  let releaseOnly = false;
  let outputDirectory;
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === "--release") {
      releaseOnly = true;
    } else if (argument === "--output") {
      outputDirectory = args[index + 1];
      if (!outputDirectory) {
        throw new Error("--output requires a directory");
      }
      index += 1;
    } else {
      throw new Error(`unknown argument: ${argument}`);
    }
  }
  return { releaseOnly, outputDirectory };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const options = parseArguments(process.argv.slice(2));
    const result = createPackage(options);
    process.stdout.write(`${JSON.stringify({ version: result.version, tarballPath: result.tarballPath })}\n`);
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  }
}
