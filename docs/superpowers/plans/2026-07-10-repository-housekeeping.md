# Repository Housekeeping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove obsolete Chainguard configuration, establish history-derived ownership, and add contribution and release guides for the Python, TypeScript, and Go SDKs.

**Architecture:** Keep the change documentation-only: `.github/CODEOWNERS` defines the reviewed ownership hierarchy, `CONTRIBUTING.md` defines repository and Python contribution boundaries, `RELEASE.md` defines the release gate and automated publishing behavior, and `README.md` routes contributors to both guides. Existing SDK implementation and tests remain unchanged.

**Tech Stack:** GitHub CODEOWNERS, GitHub Actions, Markdown, Python, TypeScript/Node.js, Go

## Global Constraints

- Remove `.github/chainguard/` completely.
- Preserve the unrelated untracked `.codex/` directory.
- Do not modify SDK implementation or test code.
- Calls to generated Python API clients belong only in `python/lightning_sdk/api/`.
- Public Python APIs must not require or optionally accept resource IDs; accept names or resource objects and resolve IDs internally.
- Every Python module must resolve to at least two CODEOWNERS.
- Do not add specific rules for `__init__.py`, `__version__.py`, `constants.py`, `exceptions.py`, `helpers.py`, tests, or `lightning_cloud`.
- Within each rule, order `@justusschock` first, then `@ethanwharris`, then `@k223kim`; order all other owners by contribution history for that file or package.
- Before a release tag is created, the release candidate must undergo automated internal integration testing.
- The first release tag on a given day is `vYYYY.MM.DD`; additional same-day releases are `vYYYY.MM.DD.post0`, then `.post1`, and so on.
- Publishing a GitHub Release automatically publishes to PyPI and npm through the existing workflows.

______________________________________________________________________

### Task 1: Remove Chainguard configuration and replace CODEOWNERS

**Files:**

- Delete: `.github/chainguard/grid-sdk-integration-read.sts.yaml`
- Delete: `.github/chainguard/grid-vendor-cloud.sts.yaml`
- Modify: `.github/CODEOWNERS`

**Interfaces:**

- Consumes: Contributor history from `../lightning-sdk` and the maintainer-reviewed priority order in the design specification.

- Produces: Repository ownership rules inherited by all later documentation changes.

- [ ] **Step 1: Capture the pre-change failure conditions**

Run:

```bash
test ! -d .github/chainguard
```

Expected: FAIL because `.github/chainguard/` still exists.

Run:

```bash
rg -n '^\* @justusschock @ethanwharris$' .github/CODEOWNERS
```

Expected: FAIL because the stale CODEOWNERS file does not contain the approved default rule.

- [ ] **Step 2: Remove the obsolete Chainguard files**

Delete both tracked files:

```text
.github/chainguard/grid-sdk-integration-read.sts.yaml
.github/chainguard/grid-vendor-cloud.sts.yaml
```

The directory disappears once both files are deleted.

- [ ] **Step 3: Replace `.github/CODEOWNERS` with the approved rules**

Write exactly:

```text
* @justusschock @ethanwharris

/.github/ @justusschock @ethanwharris @owbone

/python/ @justusschock @ethanwharris @k223kim
/python/docs/ @justusschock @dhedey
/python/examples/ @justusschock @k223kim

/python/lightning_sdk/api/ @justusschock @ethanwharris @k223kim
/python/lightning_sdk/cli/ @justusschock @ethanwharris @k223kim
/python/lightning_sdk/llm/ @k223kim @Danidapena
/python/lightning_sdk/pipeline/ @justusschock @tchaton
/python/lightning_sdk/sandbox/ @k223kim @rusenask

/python/lightning_sdk/agents.py @k223kim @Danidapena
/python/lightning_sdk/base_studio.py @justusschock @ethanwharris @viveque
/python/lightning_sdk/deployment.py @justusschock @tchaton
/python/lightning_sdk/filesystem.py @justusschock @k223kim @owbone
/python/lightning_sdk/job.py @justusschock @ethanwharris
/python/lightning_sdk/k8s_cluster.py @ethanwharris @k223kim
/python/lightning_sdk/lit_container.py @ethanwharris @k223kim
/python/lightning_sdk/machine.py @justusschock @ethanwharris
/python/lightning_sdk/mmt.py @justusschock @ethanwharris
/python/lightning_sdk/models.py @justusschock @ethanwharris
/python/lightning_sdk/organization.py @justusschock @ethanwharris @k223kim
/python/lightning_sdk/owner.py @justusschock @ethanwharris @k223kim
/python/lightning_sdk/sandbox.py @justusschock @k223kim
/python/lightning_sdk/serve.py @k223kim @tchaton
/python/lightning_sdk/status.py @justusschock @ethanwharris @k223kim
/python/lightning_sdk/studio.py @justusschock @ethanwharris @k223kim
/python/lightning_sdk/teamspace.py @justusschock @ethanwharris @k223kim
/python/lightning_sdk/user.py @justusschock @ethanwharris @k223kim

/js/ @k223kim @rusenask
/go/ @justusschock @owbone
```

- [ ] **Step 4: Verify removal, rule coverage, and module-owner counts**

Run:

```bash
test ! -d .github/chainguard
! rg -n 'chainguard|grid-sdk-integration-read|grid-vendor-cloud' . --hidden -g '!.git/**' -g '!.codex/**' -g '!docs/superpowers/**'
```

Expected: PASS with no output.

Run:

```bash
while IFS= read -r pattern; do
  [ "$pattern" = "*" ] && continue
  path="${pattern#/}"
  path="${path%/}"
  test -e "$path" || { echo "Missing CODEOWNERS path: $pattern"; exit 1; }
done < <(awk 'NF && $1 !~ /^#/ {print $1}' .github/CODEOWNERS)
```

Expected: PASS with no output.

Run:

```bash
awk '$1 ~ /^\/python\/lightning_sdk\/.*\.py$/ && NF < 3 {print "Too few owners:", $0; failed=1} END {exit failed}' .github/CODEOWNERS
```

Expected: PASS with no output; each explicit module line has a path plus at least two owners. Modules without explicit rules inherit the three-owner `/python/` rule.

- [ ] **Step 5: Verify GitHub permissions for every named owner**

Run:

```bash
for owner in justusschock ethanwharris k223kim owbone dhedey Danidapena tchaton rusenask viveque; do
  gh api "repos/Lightning-AI/sdk/collaborators/$owner/permission" --jq '"\(.user.login)\t\(.permission)"'
done
```

Expected: every owner reports `write`, `maintain`, or `admin`. If `viveque` still reports `read`, stop and report that the approved `base_studio.py` ownership cannot yet be enforced; do not silently remove him.

- [ ] **Step 6: Commit the ownership and cleanup change**

```bash
git add .github/CODEOWNERS .github/chainguard/grid-sdk-integration-read.sts.yaml .github/chainguard/grid-vendor-cloud.sts.yaml
git diff --cached --check
git commit -m "chore: update code ownership and remove chainguard config"
```

Expected: one commit containing only `.github/CODEOWNERS` and deletion of the two Chainguard files.

### Task 2: Add the contribution guide

**Files:**

- Create: `CONTRIBUTING.md`

**Interfaces:**

- Consumes: Existing package layouts and commands from `python/README.md`, `js/README.md`, `go/README.md`, and CI workflows.

- Produces: Repository-wide contribution expectations and the public Python API boundary used during review.

- [ ] **Step 1: Capture the missing-guide condition**

Run:

```bash
test -f CONTRIBUTING.md
```

Expected: FAIL because the repository has no contribution guide.

- [ ] **Step 2: Create `CONTRIBUTING.md`**

Write exactly:

````markdown
# Contributing to Lightning SDK

Thank you for contributing to the Lightning SDK. Keep changes focused on one
SDK or one shared concern, and include tests and documentation when behavior
changes.

## Repository structure

- `python/` contains the Python SDK, CLI, tests, examples, and documentation.
- `js/` contains the TypeScript SDK for Lightning AI sandboxes.
- `go/` contains the Go SDK and its generated internal API client.

The package-specific READMEs contain additional setup and usage information:
[`python/README.md`](python/README.md), [`js/README.md`](js/README.md), and
[`go/README.md`](go/README.md).

## Development checks

Install the Python package from the repository root and run its tests from the
test directory:

```bash
pip install -r python/tests/requirements.txt
pip install -e "./python[serve]"
cd python/tests
pytest . -vv -s
```

Build and test the TypeScript package:

```bash
cd js
npm ci
npm run build
npm test
```

Test the Go package:

```bash
cd go
go test -count=1 ./...
```

Run the checks relevant to the files you changed. Before opening a pull request,
run the repository hooks when available:

```bash
pre-commit run --all-files
```

## Python architecture

### Keep generated API calls in `lightning_sdk.api`

Only modules in `python/lightning_sdk/api/` may call the generated API clients.
Public modules must use that API layer instead of importing or calling generated
clients from `python/lightning_sdk/lightning_cloud/` directly. This keeps
generated transport details out of the public SDK surface.

### Accept names, not IDs

Public Python APIs must not require or optionally accept opaque resource IDs
from users. Accept user-facing names or resource objects and resolve the
corresponding IDs internally through the API layer. IDs may be used internally
or exposed as returned resource state, but users must not need to supply them to
perform an operation.

Tests should exercise the public name-based behavior and mock generated-client
interactions behind the API layer.

## Pull requests

- Keep changes scoped and avoid unrelated cleanup.
- Add or update focused tests for behavior changes.
- Update public documentation when an API or workflow changes.
- Confirm formatting, tests, and package builds relevant to the change pass.
````

- [ ] **Step 3: Verify the contribution requirements are explicit**

Run:

```bash
rg -n '^## Repository structure$|^## Python architecture$|Only modules in `python/lightning_sdk/api/`|must not require or optionally accept opaque resource IDs' CONTRIBUTING.md
```

Expected: four matches covering repository structure and both Python constraints.

Run:

```bash
pre-commit run mdformat --files CONTRIBUTING.md
git diff --check -- CONTRIBUTING.md
```

Expected: both commands pass. Re-read the formatted file if `mdformat` changes it.

- [ ] **Step 4: Commit the contribution guide**

```bash
git add CONTRIBUTING.md
git diff --cached --check
git commit -m "docs: add contribution guide"
```

Expected: one commit containing only `CONTRIBUTING.md`.

### Task 3: Add the release guide and route readers from the README

**Files:**

- Create: `RELEASE.md`
- Modify: `README.md:272-302`

**Interfaces:**

- Consumes: `.github/workflows/release.yaml` for PyPI and `.github/workflows/release-npm.yaml` for npm.

- Produces: A maintainer-facing pre-tag gate and discoverable links to both repository guides.

- [ ] **Step 1: Capture the missing release documentation**

Run:

```bash
test -f RELEASE.md
```

Expected: FAIL because the repository has no release guide.

Run:

```bash
rg -n 'CONTRIBUTING\.md|RELEASE\.md' README.md
```

Expected: FAIL because the root README links neither guide.

- [ ] **Step 2: Create `RELEASE.md`**

Write exactly:

```markdown
# Releasing Lightning SDK

Lightning SDK releases are published automatically from GitHub Releases.

## Before tagging

Every release candidate must undergo automated internal integration testing
before a release tag is created. Do not create or push the tag until that
testing has completed successfully.

## Tag format

Tags use calendar versions with a `v` prefix:

- The first release on a given day is `vYYYY.MM.DD`.
- The second release that day is `vYYYY.MM.DD.post0`.
- Further releases increment the suffix sequentially: `.post1`, `.post2`, and
  so on.

## Publish the release

After automated internal integration testing succeeds:

1. Create the release tag.
2. Create and publish a GitHub Release for that tag.
3. Monitor the GitHub Actions runs until both publishing workflows complete.

Publishing the GitHub Release triggers the existing automation:

- [`.github/workflows/release.yaml`](.github/workflows/release.yaml) builds the
  Python distribution and publishes `lightning-sdk` to PyPI.
- [`.github/workflows/release-npm.yaml`](.github/workflows/release-npm.yaml)
  builds the TypeScript distribution and publishes `@lightningai/sdk` to npm.

The GitHub Release is the publishing mechanism; normal releases do not require
manual uploads to PyPI or npm.
```

- [ ] **Step 3: Link both guides from the root README**

After the package-specific README paragraph in the `Development` section, add:

```markdown

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for repository-wide contribution
requirements and development checks.
```

At the end of the `Community` section, add:

```markdown

Maintainers preparing a release should follow [`RELEASE.md`](RELEASE.md).
```

- [ ] **Step 4: Verify the release claims against the workflows**

Run:

```bash
rg -n 'release:|types: \[published\]|gh-action-pypi-publish' .github/workflows/release.yaml
rg -n 'release:|types: \[published\]|npm publish' .github/workflows/release-npm.yaml
```

Expected: each workflow listens for a published GitHub Release; the Python workflow uses `gh-action-pypi-publish`, and the npm workflow runs `npm publish`.

Run:

```bash
rg -n 'automated internal integration testing|vYYYY\.MM\.DD|\.post0|GitHub Release|PyPI|npm' RELEASE.md
rg -n 'CONTRIBUTING\.md|RELEASE\.md' README.md
```

Expected: the release guide contains the testing gate and both publishing targets, and the README links both guides.

Run:

```bash
pre-commit run mdformat --files RELEASE.md README.md
git diff --check -- RELEASE.md README.md
```

Expected: both commands pass. Re-read both files if `mdformat` changes them.

- [ ] **Step 5: Commit the release guide and README links**

```bash
git add RELEASE.md README.md
git diff --cached --check
git commit -m "docs: document automated releases"
```

Expected: one commit containing only `RELEASE.md` and `README.md`.

### Task 4: Run final repository verification

**Files:**

- Verify: `.github/CODEOWNERS`
- Verify: `CONTRIBUTING.md`
- Verify: `RELEASE.md`
- Verify: `README.md`
- Verify deletion: `.github/chainguard/`

**Interfaces:**

- Consumes: The completed outputs from Tasks 1-3.

- Produces: Evidence that the housekeeping change is internally consistent and contains no unrelated edits.

- [ ] **Step 1: Run formatting and repository hygiene checks**

Run:

```bash
pre-commit run --all-files
git diff --check HEAD~3..HEAD
```

Expected: all hooks pass and Git reports no whitespace errors.

- [ ] **Step 2: Re-run the focused acceptance checks**

Run:

```bash
test ! -d .github/chainguard
! rg -n 'chainguard|grid-sdk-integration-read|grid-vendor-cloud' . --hidden -g '!.git/**' -g '!.codex/**' -g '!docs/superpowers/**'
rg -n '^\* @justusschock @ethanwharris$' .github/CODEOWNERS
rg -n 'Only modules in `python/lightning_sdk/api/`|must not require or optionally accept opaque resource IDs' CONTRIBUTING.md
rg -n 'automated internal integration testing|vYYYY\.MM\.DD|\.post0|GitHub Release|PyPI|npm' RELEASE.md
rg -n 'CONTRIBUTING\.md|RELEASE\.md' README.md
```

Expected: all commands pass; searches print the approved ownership rule, both Python architecture requirements, the release gate, tag convention, publishing targets, and both README links.

- [ ] **Step 3: Confirm the final commit range and worktree scope**

Run:

```bash
git status --short
git diff --stat a4e0fc21..HEAD
git diff --name-status a4e0fc21..HEAD
```

Expected: `.codex/` is the only untracked path. The implementation commits change only `.github/CODEOWNERS`, the two deleted `.github/chainguard/` files, `CONTRIBUTING.md`, `RELEASE.md`, and `README.md`, in addition to the already committed design and plan documents.

- [ ] **Step 4: Record verification evidence**

Update the Obsidian agent-memory state with:

```text
Repository housekeeping implemented. Chainguard configuration removed; ordered CODEOWNERS installed; CONTRIBUTING.md documents TypeScript, Python, and Go structure plus Python API boundaries; RELEASE.md requires automated internal integration testing before tagging and documents GitHub Release-driven PyPI/npm publishing. Record pre-commit result, focused acceptance checks, commit hashes, and the remaining untracked .codex/ directory.
```

No additional repository commit is needed unless verification changes a tracked file.
