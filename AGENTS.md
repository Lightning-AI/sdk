# Agent instructions

Guidance for AI coding agents working in this repository. `CLAUDE.md` is a
symlink to this file.

## This repository is public

Everything written here is published: code, comments, docs, commit messages,
pull request titles and descriptions, review comments and issues. Anyone can
read it, and it stays in the git history even after it is edited or deleted.

Describe the code: what changed, how it behaves now, and why that is the right
design. Leave out how the work came about. Do not include:

- Who asked for the change, which customer or team it is for, or who approved
  it.
- Links to or references from private systems: private repositories and their
  pull requests or issues, chat threads, internal docs, dashboards or trackers.
- Internal ticket numbers, incident names, rollout or release plans, or other
  details of internal process.
- Internal hostnames, cluster, organization or user names and IDs, and any
  credentials or tokens.

A reason grounded in the code or in what users see belongs in the description:

> `studio delete` now checks that the user may delete Studios before asking for
> confirmation, so users without permission get a clear error instead of a 403.

A reason grounded in internal context does not:

> A customer reported this in support; needed for next week's rollout, see the
> linked internal PR.

If a change only makes sense with internal context, describe its behavior here
and keep the context in internal channels. When unsure whether something is
internal, leave it out.

The same applies to human contributors; see
[`CONTRIBUTING.md`](CONTRIBUTING.md#pull-requests).

## Development

[`CONTRIBUTING.md`](CONTRIBUTING.md) covers the repository layout, how to run
the checks for each SDK, and the architecture rules for the Python SDK. Follow
it.
