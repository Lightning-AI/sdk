"""Studio switch command."""

from typing import Optional

import click

from lightning_sdk.cli.utils.save_to_config import save_teamspace_to_config
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
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
    menu = TeamspacesMenu()
    resolved_teamspace = menu(teamspace=teamspace)
    save_teamspace_to_config(resolved_teamspace, overwrite=False)

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
