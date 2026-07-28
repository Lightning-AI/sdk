"""Shared --teamspace CLI option, plus the single resolution helper backing every command."""

from typing import Callable, Optional, TypeVar

import rich_click as click

from lightning_sdk.cli.utils.save_to_config import save_teamspace_to_config
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.utils.resolve import _resolve_teamspace

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
    """Resolve CLI teamspace options into a single Teamspace instance.

    This is the one shared entry point CLI commands use to turn
    ``--teamspace``/``--org``/``--user`` into a ``Teamspace``. It supports:

    * The modern convention: ``--teamspace`` alone, either a bare name (uses the
      configured/default owner, or falls back to an interactive picker) or an
      ``owner/teamspace`` slug (unambiguous, no picker).
    * The deprecated convention: ``--org``/``--user`` supplied alongside a bare
      ``--teamspace`` name, preserved for backward compatibility during the
      deprecation window.
    """
    if org is not None or user is not None:
        if teamspace and "/" in teamspace:
            raise click.UsageError(
                "--teamspace was given in 'owner/teamspace' format, which already specifies the "
                "owner. Remove --org/--user, or drop the 'owner/' prefix from --teamspace and keep "
                "--org/--user."
            )
        resolved_teamspace = _resolve_teamspace(teamspace, org, user)
    else:
        resolved_teamspace = TeamspacesMenu()(teamspace=teamspace)

    save_teamspace_to_config(resolved_teamspace, overwrite=False)
    return resolved_teamspace


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
