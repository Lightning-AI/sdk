"""Studio switch command."""

from typing import Optional

import click

from lightning_sdk.cli.utils.resolve import resolve_teamspace_owner_name_format
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.machine import Machine
from lightning_sdk.studio import Studio


@click.command("switch")
@click.argument("studio_name", required=False)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
@click.option(
    "--machine",
    help="The machine type to switch the studio to.",
    type=click.Choice(m.name for m in Machine.__dict__.values() if isinstance(m, Machine)),
)
@click.option("--interruptible", is_flag=True, help="Switch the studio to an interruptible instance.")
def switch_studio(
    studio_name: Optional[str] = None,
    teamspace: Optional[str] = None,
    machine: Optional[str] = None,
    interruptible: bool = False,
) -> None:
    """Switch a Studio to a different machine type."""
    if teamspace is not None:
        resolved_teamspace = resolve_teamspace_owner_name_format(teamspace)
        if resolved_teamspace is None:
            raise ValueError(
                f"Could not resolve teamspace: '{teamspace}'. Teamspace should be specified as 'owner/name'. "
                "Does the teamspace exist?"
            )
    else:
        resolved_teamspace = None

    try:
        studio = Studio(
            studio_name,
            teamspace=resolved_teamspace,
        )
    except (RuntimeError, ValueError, ApiException):
        if studio_name:
            raise ValueError(f"Could not switch Studio: '{studio_name}'. Does the Studio exist?") from None
        raise ValueError(f"Could not switch Studio: '{studio_name}'. Please provide a Studio name") from None

    resolved_machine = Machine.from_str(machine)
    Studio.show_progress = True
    studio.switch_machine(resolved_machine, interruptible=interruptible)

    click.echo(f"Studio '{studio.name}' switched to machine '{resolved_machine}' successfully")
