"""Shared JSON output for CLI commands.

Every command's ``--json`` path should render through :func:`echo_json` so machine
output is byte-for-byte consistent across the CLI.
"""

import json

import rich_click as click


def _default(value: object) -> str:
    return str(value)


def echo_json(payload: object) -> None:
    """Print ``payload`` as indented, key-sorted JSON on stdout."""
    click.echo(json.dumps(payload, default=_default, indent=2, sort_keys=True))
