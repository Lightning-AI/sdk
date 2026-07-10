# Command Line Interface

The Python package installs the `lightning` command. The `lightning-sdk`
console script is an alias for the same command group.

Use the CLI when you want to manage Lightning AI resources from a terminal,
CI job, shell script, or other automation. The command reference below is
generated from the Click command tree, so command groups, options, arguments,
and examples stay aligned with the installed package.

The live command tree below is expanded at documentation build time. Click
Extra supplies the headings and terminal fences, while the imported command
object remains the SDK's existing `rich-click` CLI.

Legacy aliases that only emit a migration error are intentionally omitted;
their supported noun-first replacements are documented instead.

```{click:tree} main_cli
:root-label: lightning --help
:anchor-prefix: lightning
from lightning_sdk.cli.entrypoint import main_cli
```

## Install

Install or upgrade the Python package:

```{code-block} bash
pip install lightning-sdk -U
```

## Authenticate

For interactive use, sign in with:

```{code-block} bash
lightning login
```

For non-interactive environments, configure credentials through environment
variables instead:

```{code-block} bash
export LIGHTNING_USER_ID=your-user-id
export LIGHTNING_API_KEY=your-api-key
```

## Usage

Run a command group directly:

```{code-block} bash
lightning [command]
```

Every command and subcommand exposes help from the same Click definitions used
by this reference:

```{code-block} bash
lightning COMMAND --help
```

## Common Workflows

- Develop interactively with {doc}`studio`.
- Submit and inspect training or batch work with {doc}`job` and {doc}`mmt`.
- Build and operate inference services with {doc}`deployment` and {doc}`model`.
- Move data and artifacts with {doc}`file`, {doc}`folder`, {doc}`container`, and {doc}`cp`.
- Configure accounts, organizations, teamspaces, cloud accounts, and SSH with
  {doc}`config`, {doc}`api-key`, and {doc}`ssh`.
- Manage lower-level sandbox sessions with {doc}`sandbox`.

## Command details

The pages below keep focused URLs for each command group and its full option
reference.

```{toctree}
:maxdepth: 1

config
job
mmt
machine
deployment
container
model
api-key
file
folder
ssh
studio
sandbox
base-studio
license
cp
```
