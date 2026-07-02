# Python Examples

This directory keeps SDK tutorials and CLI examples separate. Use the Python
files and their paired `.rst` pages when writing SDK automation. Use the
`*_cli.rst` pages when you want terminal commands for scripts or CI.

The SDK examples are executable Python files. Their paired `.rst` tutorials
include selected code blocks from those files, so the documented snippets stay
close to runnable code.

The examples use placeholder names such as `owner/teamspace` and
`sdk-tutorial-studio`. Replace them with resources that exist in your Lightning
AI account. Authenticate once with `lightning login` before using the CLI or SDK
examples. Sandbox examples use the sandbox API key path instead; set
`LIGHTNING_SANDBOX_API_KEY` or pass `--api-key` without committing the key to
source control.

## SDK Tutorials

- `studios.rst` and `studios.py`: create, start, use, and stop persistent Studio workspaces.
- `jobs.rst` and `jobs.py`: submit, inspect, wait for, and clean up single-machine jobs.
- `mmts.rst` and `mmts.py`: run and inspect multi-machine training jobs.
- `teamspaces.rst` and `teamspaces.py`: choose account context and inspect teamspace resources.
- `sandboxes.rst` and `sandboxes.py`: create disposable or persistent sandboxes and run commands.

## CLI Examples

- `studios_cli.rst`: create, start, connect to, copy files into, and stop Studios from the CLI.
- `jobs_cli.rst`: submit, inspect, list, stop, and delete jobs from the CLI.
- `mmts_cli.rst`: launch and inspect multi-machine training runs from the CLI.
- `teamspaces_cli.rst`: set CLI context and pass explicit teamspace scope to resource commands.
- `sandboxes_cli.rst`: create sandboxes, run commands, inspect logs, stop, resume, and delete from the CLI.
