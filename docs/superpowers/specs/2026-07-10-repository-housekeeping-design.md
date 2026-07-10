# Repository Housekeeping Design

## Goal

Make the repository easier to maintain by removing obsolete Chainguard configuration, documenting contribution expectations across the TypeScript, Python, and Go SDKs, and replacing the stale CODEOWNERS rules with ownership derived from the `lightning-sdk` commit history and refined by maintainer review.

## Scope

- Remove the two files under `.github/chainguard/` and leave no empty directory behind.
- Add root `CONTRIBUTING.md` and `RELEASE.md` guides and link them from the root `README.md`.
- Replace `.github/CODEOWNERS` with the approved ownership rules below.
- Do not modify SDK implementation or test code.
- Preserve the unrelated untracked `.codex/` directory.

## Contribution Guide

The guide will describe the repository as three SDK implementations:

- TypeScript under `js/`
- Python under `python/`
- Go under `go/`

It will direct contributors to the language-specific development configuration and commands already present in each subtree instead of duplicating extensive setup instructions.

The Python section will state these architectural requirements explicitly:

1. Calls to generated API clients belong only in the `lightning_sdk.api` subpackage. Public modules use that layer instead of calling generated clients directly.
2. Public Python APIs must not require or optionally accept opaque resource IDs from users. They accept names or resource objects and resolve the corresponding IDs internally.
3. Tests should cover the public name-based behavior and keep generated-client interactions behind the API layer.

## Release Guide

The release guide will document the required sequence without duplicating the GitHub Actions implementation:

1. Every release candidate must undergo automated internal integration testing before a release tag is created.
2. A tag and GitHub Release may be created only after that testing succeeds.
3. Publishing the GitHub Release triggers the existing workflows that publish the Python package to PyPI and the TypeScript package to npm automatically.

The guide will link to `.github/workflows/release.yaml` and `.github/workflows/release-npm.yaml` as the source of truth for the publishing automation.

## CODEOWNERS Ordering

Within each rule, owners are ordered by priority:

1. `@justusschock`
2. `@ethanwharris`
3. `@k223kim`
4. Other owners ordered according to their contribution history for that file or package

The approved rules are:

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

`__init__.py`, `__version__.py`, `constants.py`, `exceptions.py`, `helpers.py`, tests, and `lightning_cloud` intentionally have no more-specific rule and inherit `/python/`. Every Python module therefore has at least three inherited owners or at least two explicit owners.

`@viveque` currently needs write access to `Lightning-AI/sdk` before GitHub can enforce the `base_studio.py` rule; the repository owner will grant that access.

## Verification

- Confirm `.github/chainguard/` is absent and no repository file refers to the removed configuration.
- Validate that every CODEOWNERS path exists, except paths intentionally acting as subtree patterns.
- Confirm all named CODEOWNERS have write access after `@viveque` is upgraded.
- Check owner ordering and ensure every explicit module rule contains at least two owners.
- Check that the contribution guide describes all three language trees and contains both Python architectural requirements.
- Check that the release guide makes automated internal integration testing a pre-tag requirement and accurately describes GitHub Release-based PyPI and npm publishing.
- Run Markdown formatting or lint checks available in the repository, plus `git diff --check`.
- Review the final diff to ensure only the approved housekeeping files changed.
