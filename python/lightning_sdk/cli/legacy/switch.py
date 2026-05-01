from typing import Optional

import click

from lightning_sdk import Machine, Studio
from lightning_sdk.lightning_cloud.openapi.rest import ApiException

_MACHINE_VALUES = tuple(
    [machine.name for machine in Machine.__dict__.values() if isinstance(machine, Machine) and machine._include_in_cli]
)


@click.group("switch")
def switch() -> None:
    """Switch machines for resources on the Lightning AI platform."""


@switch.command("studio")
@click.argument("name")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "The teamspace the studio is part of. "
        "Should be of format <OWNER>/<TEAMSPACE_NAME>. "
        "If not specified, tries to infer from the environment (e.g. when run from within a Studio.)"
    ),
)
@click.option(
    "--machine",
    default="CPU",
    show_default=True,
    type=click.Choice(_MACHINE_VALUES),
    help="The machine type to switch to.",
)
def studio(name: str, teamspace: Optional[str] = None, machine: str = "CPU") -> None:
    """Switch a studio to a given machine.

    Example:
      lightning switch studio NAME --machine=CPU

    NAME: the name of the studio to switch machine for.
    """
    if teamspace is not None:
        ts_splits = teamspace.split("/")
        if len(ts_splits) != 2:
            raise ValueError(f"Teamspace should be of format <OWNER>/<TEAMSPACE_NAME> but got {teamspace}")
        owner, teamspace = ts_splits
    else:
        owner, teamspace = None, None

    try:
        studio = Studio(name=name, teamspace=teamspace, org=owner, user=None, create_ok=False)
    except (RuntimeError, ValueError, ApiException):
        studio = Studio(name=name, teamspace=teamspace, org=None, user=owner, create_ok=False)

    try:
        resolved_machine = getattr(Machine, machine.upper(), Machine(machine, machine))
    except KeyError:
        resolved_machine = machine

    Studio.show_progress = True
    studio.switch_machine(resolved_machine)
