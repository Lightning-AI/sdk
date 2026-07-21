import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { parseDescribe, renderVersion } from "../scripts/scm-version.mjs";

describe("SCM version rendering", () => {
  it("renders an exact CalVer tag", () => {
    assert.equal(renderVersion(parseDescribe("v2026.07.09-0-gabc1234")), "2026.7.9");
  });

  it("renders an exact post-release tag", () => {
    assert.equal(renderVersion(parseDescribe("v2026.07.09.post0-0-gabc1234")), "2026.7.9-post0");
  });

  it("includes distance and hash after a CalVer tag", () => {
    assert.equal(renderVersion(parseDescribe("v2026.07.09-3-gabc1234")), "2026.7.10-dev.3+gabc1234");
  });

  it("increments the post release for development commits", () => {
    assert.equal(
      renderVersion(parseDescribe("v2026.07.09.post0-3-gabc1234")),
      "2026.7.9-post1.dev.3+gabc1234",
    );
  });

  it("marks dirty development versions with a UTC date", () => {
    assert.equal(
      renderVersion(parseDescribe("v2026.07.09-3-gabc1234-dirty"), new Date("2026-07-21T00:00:00Z")),
      "2026.7.10-dev.3+gabc1234.d20260721",
    );
  });

  it("does not reuse an exact release version for a dirty checkout", () => {
    assert.equal(
      renderVersion(parseDescribe("v2026.07.09.post0-0-gabc1234-dirty"), new Date("2026-07-21T00:00:00Z")),
      "2026.7.9-post1.dev.0+gabc1234.d20260721",
    );
  });

  it("renders a traceable fallback when no release tag exists", () => {
    assert.equal(
      renderVersion({ tag: null, distance: 5, hash: "40e8d78", dirty: false }),
      "0.0.0-dev.5+g40e8d78",
    );
  });

  it("rejects unsupported tag formats", () => {
    assert.throws(() => parseDescribe("release-2026.07.09-0-gabc1234"), /unsupported version tag/);
    assert.throws(() => parseDescribe("v2026.7.9-0-gabc1234"), /unsupported version tag/);
  });
});
