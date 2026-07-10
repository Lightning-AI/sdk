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
