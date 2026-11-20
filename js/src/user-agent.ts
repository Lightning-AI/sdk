import { readFileSync } from "node:fs";

/**
 * Names this SDK and its release, which the platform checks against the
 * minimum JS SDK it supports. A release stamps its version into the packaged
 * package.json after the code is compiled, so it's read from there at run
 * time. "dev", when that file can't be found, counts as older than every
 * release.
 */
export const USER_AGENT = `lightning-sdk-js/${packageVersion()}`;

function packageVersion(): string {
  try {
    const manifest = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as {
      name?: unknown;
      version?: unknown;
    };
    // A bundler can place this file beside another package's manifest.
    if (manifest.name === "@lightningai/sdk" && typeof manifest.version === "string" && manifest.version !== "") {
      return manifest.version;
    }
  } catch {
    // Bundled or relocated, with no manifest to read.
  }
  return "dev";
}
