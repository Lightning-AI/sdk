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
1. Create and publish a GitHub Release for that tag.
1. Monitor the GitHub Actions runs until both publishing workflows complete.

Publishing the GitHub Release triggers the existing automation:

- [`.github/workflows/release.yaml`](.github/workflows/release.yaml) builds the
  Python distribution and publishes `lightning-sdk` to PyPI.
- [`.github/workflows/release-npm.yaml`](.github/workflows/release-npm.yaml)
  builds the TypeScript distribution and publishes `@lightningai/sdk` to npm.

The GitHub Release is the publishing mechanism; normal releases do not require
manual uploads to PyPI or npm.
