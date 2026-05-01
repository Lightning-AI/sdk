import random
import string
from contextlib import suppress
from typing import Optional

import click
from rich.console import Console

from lightning_sdk import Machine, Studio
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.machine import CloudProvider

_MACHINE_VALUES = tuple(
    [machine.name for machine in Machine.__dict__.values() if isinstance(machine, Machine) and machine._include_in_cli]
)
_PROVIDER_VALUES = tuple([provider.value for provider in CloudProvider])


@click.group("create")
def create() -> None:
    """Create new resources on the Lightning AI platform."""


@create.command("studio")
@click.argument("name")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "The teamspace the studio will be part of. "
        "Should be of format <OWNER>/<TEAMSPACE_NAME>. "
        "If not specified, tries to infer from the environment (e.g. when run from within a Studio.)"
    ),
)
@click.option(
    "--start",
    default=None,
    type=click.Choice(_MACHINE_VALUES),
    help="If specified, will start the created studio on the given machine.",
)
@click.option(
    "--cloud-account",
    "--cloud_account",
    default=None,
    help=(
        "The cloud account to create the studio on. "
        "If not specified, will try to infer from the environment (e.g. when run from within a Studio.) "
        "or fall back to the teamspace default."
    ),
)
@click.option(
    "--cloud-provider",
    default=None,
    type=click.Choice(_PROVIDER_VALUES),
    help="The provider to create the studio on. If --cloud-account is specified, this option is prioritized.",
)
@click.option(
    "--provider",
    default=None,
    type=click.Choice(_PROVIDER_VALUES),
    help=(
        "Deprecated. Use --cloud-provider instead. The provider to create the studio on. "
        "If --cloud-account is specified, this option is prioritized."
    ),
)
def studio(
    name: str,
    teamspace: Optional[str] = None,
    start: Optional[str] = None,
    cloud_account: Optional[str] = None,
    cloud_provider: Optional[str] = None,
    provider: Optional[str] = None,
) -> None:
    """Create a new studio on the Lightning AI platform.

    Example:
        lightning create studio NAME

    NAME: the name of the studio to create. If already present within teamspace, will add a random suffix.
    """
    menu = TeamspacesMenu()
    teamspace_resolved = menu(teamspace)

    # default cloud account to current studios cloud account if run from studio
    # else it will fall back to teamspace default in the backend
    if cloud_account is None:
        with suppress(ValueError):
            s = Studio()
            if s.teamspace.name == teamspace_resolved.name and s.teamspace.owner.name == teamspace_resolved.owner.name:
                cloud_account = s.cloud_account

    console = Console()

    with suppress(ValueError):
        Studio(name, teamspace=teamspace_resolved, create_ok=False)
        new_name = name + "-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        console.print(f"Studio with name {name} already exists. Using {new_name} instead.")
        name = new_name

    studio = Studio(
        name=name,
        teamspace=teamspace_resolved,
        cloud_account=cloud_account,
        create_ok=True,
        cloud_provider=cloud_provider,
        provider=provider,
    )

    console.print(f"Created Studio {studio.name}.")

    if start is not None:
        start_machine = getattr(Machine, start, start)
        Studio.show_progress = True
        studio.start(start_machine)
        console.print(f"Started Studio {studio.name} on machine {start}")
