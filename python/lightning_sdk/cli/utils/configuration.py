"""Shared parsing and rendering records for environment and secret commands."""

import re
import sys
from typing import Dict, List, Tuple, Union

import rich_click as click

from lightning_sdk.api.deployment_api import Env, Secret

VARIABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_name(name: str) -> None:
    """Validate an environment variable or generic secret name."""
    if VARIABLE_NAME_PATTERN.fullmatch(name) is None:
        raise click.BadParameter(
            "Names must start with a letter or underscore and contain only letters, numbers, and underscores."
        )


def parse_assignment(assignment: str) -> Tuple[str, str]:
    """Parse a ``KEY=VALUE`` assignment, preserving empty values."""
    if "=" not in assignment:
        raise click.BadParameter("Expected KEY=VALUE.")
    key, value = assignment.split("=", 1)
    validate_name(key)
    return key, value


def read_secret_value(value_stdin: bool) -> str:
    """Read a secret from stdin or a hidden interactive prompt."""
    value = sys.stdin.read() if value_stdin else click.prompt("Secret value", hide_input=True, err=True)
    if value_stdin:
        value = value.removesuffix("\n").removesuffix("\r")
    if value == "":
        raise click.UsageError("Secret value cannot be empty.")
    return value


def secret_records(secrets: Dict[str, str]) -> List[Dict[str, str]]:
    """Build sorted, always-redacted generic secret records."""
    return [{"name": name, "value": "***REDACTED***"} for name in sorted(secrets)]


def environment_records(env: Dict[str, str]) -> List[Dict[str, str]]:
    """Build sorted literal environment-variable records."""
    return [{"name": name, "value": env[name]} for name in sorted(env)]


def deployment_environment_records(entries: List[Union[Env, Secret]]) -> List[Dict[str, str]]:
    """Build sorted records for Deployment literals and secret references."""
    records = [
        {"name": entry.name, "value": entry.value}
        if isinstance(entry, Env)
        else {"name": entry.env_var_name, "from_secret": entry.name}
        for entry in entries
    ]
    return sorted(records, key=lambda record: record["name"])


def deployment_secret_records(entries: List[Union[Env, Secret]]) -> List[Dict[str, str]]:
    """Build sorted records for Deployment secret references only."""
    records = [
        {"name": entry.env_var_name, "from_secret": entry.name} for entry in entries if isinstance(entry, Secret)
    ]
    return sorted(records, key=lambda record: record["name"])
