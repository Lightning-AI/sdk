"""Shared --teamspace CLI option, plus the single resolution helper backing every command."""

from typing import Callable, Optional, TypeVar

import rich_click as click

from lightning_sdk.cli.utils.resource_resolution import resolve_teamspace as _resolve_cli_teamspace
from lightning_sdk.cli.utils.save_to_config import save_teamspace_to_config
from lightning_sdk.teamspace import Teamspace

F = TypeVar("F", bound=Callable)

_OWNER_DEPRECATION_MESSAGE = (
    "Pass the owner as part of --teamspace instead, e.g. '--teamspace owner/teamspace'. "
    "This option will be removed in a future release."
)


def resolve_teamspace(
    teamspace: Optional[str] = None,
    org: Optional[str] = None,
    user: Optional[str] = None,
) -> Teamspace:
    resolved = _resolve_cli_teamspace(teamspace=teamspace, org=org, user=user)
    save_teamspace_to_config(resolved, overwrite=False)
    return resolved


_TEAMSPACE_OPTIONS = [
    click.option(
        "--teamspace",
        default=None,
        help="The teamspace to use, as a bare name or an 'owner/teamspace' slug. Defaults to the current teamspace.",
    ),
    click.option(
        "--org",
        default=None,
        deprecated=_OWNER_DEPRECATION_MESSAGE,
        help="The organization owning the teamspace (if any). Defaults to the current organization.",
    ),
    click.option(
        "--user",
        default=None,
        deprecated=_OWNER_DEPRECATION_MESSAGE,
        help="The user owning the teamspace (if any). Defaults to the current user.",
    ),
]


def teamspace_option(command: F) -> F:
    """Adds --teamspace plus deprecated --org/--user options to a click command."""
    for option in reversed(_TEAMSPACE_OPTIONS):
        command = option(command)
    return command
