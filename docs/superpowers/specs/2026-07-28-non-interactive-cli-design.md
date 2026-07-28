# Non-Interactive CLI Design

**Status:** Approved

**Date:** 2026-07-28

## Goal

Make every ordinary Lightning SDK CLI command deterministic and non-interactive, remove terminal-menu dependencies, and retain interaction only where the user explicitly asks for an interactive session.

## Scope

This change covers the Python CLI exported by `lightning` and `lightning-sdk`. The JavaScript and Go packages do not export CLI entry points and require no changes.

The approved interactive exceptions are:

- `lightning login`, whose explicit purpose is browser authentication.
- `lightning studio ssh` and `lightning studio connect`, whose explicit purpose is an interactive remote terminal.
- Raw API input requested with `@-` or `--input -`.
- Log streaming requested with `job logs --follow`.

Progress output is not user input and remains unchanged.

## Resource resolution architecture

Replace the menu-oriented resolver classes with typed functions in a unified `lightning_sdk.cli.utils.resource_resolution` module:

- `resolve_teamspace`
- `resolve_studio`
- `resolve_job`
- `resolve_mmt`
- `resolve_cluster`

There is no standalone `resolve_owner`. The recent `owner/teamspace` unification makes owner resolution an internal part of teamspace resolution:

- `owner/teamspace` is the canonical explicit teamspace form.
- A bare teamspace may use existing environment or configuration defaults.
- Deprecated `--org` and `--user` inputs remain supported during their existing compatibility window.
- Filesystem helpers combine a parsed owner and teamspace into `owner/teamspace` before calling `resolve_teamspace`.
- `owner_selection.py` and its menu class are removed.

`teamspace_option.py` remains responsible for the Click option decorator. It delegates resolution to the unified module and may re-export `resolve_teamspace` to avoid unnecessary call-site churn.

Every resolver follows the same precedence:

1. Use an explicit identifier when supplied.
2. Use an existing environment, configuration, or resource default where that resource already defines one.
3. Perform an exact SDK lookup.
4. Raise `click.UsageError`.

Resolvers never enumerate resources to choose one, never auto-select the only available resource, and never read from the terminal.

The resource-specific rules are:

- Teamspace: resolve an explicit or configured teamspace, including `owner/teamspace`; otherwise require `--teamspace`.
- Studio: resolve an explicit studio, the current in-studio context, or the configured studio; otherwise require the studio argument or option used by the command.
- Job: require an explicit job name and resolve it exactly within the resolved teamspace.
- Multi-machine job: require an explicit name and resolve it exactly within the resolved teamspace.
- Cluster or cloud account: use the explicit command option or `teamspace.default_cloud_account`; otherwise require the command's cloud-account option.

The legacy `_JobAndMMTAction` inheritance hierarchy is replaced with direct composition of these functions. Current commands that still import job, MMT, or cluster selection from `cli/legacy` migrate to the unified module.

## Errors

Resolution failures raise `click.UsageError` before side effects. Messages include:

- The rejected value when one was supplied.
- The resource type.
- The exact argument or option needed to correct the command.

Errors must not recommend selecting from a list, contacting Lightning support, setting `LIGHTNING_NON_INTERACTIVE`, or retrying interactively.

Underlying authentication, authorization, and transport errors retain their causal exception instead of being rewritten as a missing-resource error.

## Confirmations and acknowledgements

Commands never call `click.confirm`, `Confirm.ask`, or another prompt API.

- `deployment delete` retains its existing `--yes` requirement.
- `studio delete` gains `--yes` and fails with a usage error when it is absent.
- Hidden `api deploy` replaces `--non-interactive` with `--yes`. Dockerfile review must be acknowledged with `--yes` before build or deployment side effects begin.
- Model deployment warnings retain `--ack` and `--force`. When acknowledgement is required and neither is supplied, the command fails without a TTY prompt.

`--yes` is explicit command input and is therefore non-interactive.

## Upload recovery

Commands that can encounter incomplete folder-upload state expose mutually exclusive `--resume` and `--restart` flags. This includes `studio open` and hidden `api deploy --devbox`.

- With incomplete state and neither flag, fail with a usage error naming both choices.
- With `--resume`, load and continue the stored upload state.
- With `--resume` and no stored state, fail because there is nothing to resume.
- With `--restart`, ignore stored state and upload the current local tree from the beginning.
- With `--restart` and no stored state, start a normal fresh upload.
- With both flags, Click rejects the command before execution.

The upload helper accepts an explicit recovery policy and contains no terminal-menu code.

## Browser behavior and authentication

Only `lightning login` may launch a browser or run the local login callback server.

All other commands:

- Never call `webbrowser.open`.
- Print resource URLs for the user to open manually.
- Never initiate browser authentication.
- Fail with a clear credential error when non-browser credentials are unavailable, instructing the user to run `lightning login` explicitly.

In particular, `studio open`, API deployment, and API devbox flows print their destination URLs without opening them.

## Explicit interactive sessions and streams

`studio ssh` and `studio connect` continue to hand terminal control to the system SSH client. No other command may invoke them implicitly.

Raw API stdin and job-log following remain opt-in and unchanged. They are streaming interfaces, not selection or confirmation prompts.

## Dependency and dead-code removal

Remove:

- `simple-term-menu` from POSIX dependencies.
- `inquirer` from Windows dependencies.
- `terminal_menu_wrapper.py`.
- Menu preparation and selection methods.
- Obsolete menu-oriented selector files and legacy selector inheritance.
- Documentation mocks for the removed packages.
- `LIGHTNING_NON_INTERACTIVE` checks and documentation.
- Hidden API deploy's `--non-interactive` option.

No replacement prompt or terminal UI dependency is introduced.

## Compatibility

The change intentionally breaks workflows that relied on an implicit menu, automatic browser opening, or hidden API deploy's `--non-interactive` flag.

The following compatibility behavior remains:

- Existing explicit identifiers.
- Existing environment and configuration defaults.
- Deprecated `--org` and `--user` teamspace inputs during their current deprecation window.
- `deployment delete --yes`.
- Model deployment `--ack` and `--force`.
- Explicit login, SSH, stdin, and log-follow behavior.

Setting the retired `LIGHTNING_NON_INTERACTIVE` environment variable remains harmless because unknown environment variables are ignored.

## Testing

Implementation follows test-driven development. Each behavior change starts with a focused failing test.

Resolver tests cover:

- Explicit identifiers.
- Existing environment and configuration defaults.
- Exact lookup success.
- Missing identifiers.
- Invalid identifiers.
- Deprecated `--org` and `--user` compatibility.
- No single-resource auto-selection.
- Preservation of authentication and transport errors.

Command tests cover:

- Missing identifiers fail without terminal reads.
- Destructive operations require `--yes`.
- Model acknowledgement requires `--ack` or `--force`.
- API deploy requires `--yes` and has no `--non-interactive`.
- Upload recovery, mutual exclusion, and missing-state cases.
- URLs are printed and `webbrowser.open` is not called outside login.
- Missing credentials never start browser authentication outside login.
- Approved SSH, stdin, and log-stream behavior remains intact.

Verification consists of focused tests during each red-green-refactor cycle, the complete Python test suite, and a final source scan proving that removed menu imports, prompt APIs, dependencies, and `LIGHTNING_NON_INTERACTIVE` references are absent from the CLI.

## Non-goals

- Redesigning SDK resource resolution outside the CLI.
- Removing progress bars or status output.
- Making explicit login or SSH sessions non-interactive.
- Removing deprecated `--org` or `--user` ahead of their existing schedule.
- Refactoring unrelated legacy CLI code.
