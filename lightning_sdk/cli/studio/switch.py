"""Studio switch command."""

from typing import Optional

import click

from lightning_sdk.cli.utils.richt_print import studio_name_link
from lightning_sdk.cli.utils.save_to_config import save_studio_to_config
from lightning_sdk.cli.utils.studio_selection import StudiosMenu
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.machine import Machine


@click.command("switch")
@click.option(
    "--name",
    help=(
        "The name of the studio to switch to a different machine. "
        "If not provided, will try to infer from environment, "
        "use the default value from the config or prompt for interactive selection."
    ),
)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
@click.option(
    "--machine",
    help="The machine type to switch the studio to.",
    type=click.Choice(m.name for m in Machine.__dict__.values() if isinstance(m, Machine)),
)
@click.option("--interruptible", is_flag=True, help="Switch the studio to an interruptible instance.")
def switch_studio(
    name: Optional[str] = None,
    teamspace: Optional[str] = None,
    machine: Optional[str] = None,
    interruptible: bool = False,
) -> None:
    """Switch a Studio to a different machine type."""
    return switch_impl(
        name=name,
        teamspace=teamspace,
        machine=machine,
        interruptible=interruptible,
        vm=False,
    )


def switch_impl(
    name: Optional[str],
    teamspace: Optional[str],
    machine: Optional[str],
    interruptible: bool,
    vm: bool,
) -> None:
    menu = TeamspacesMenu()
    resolved_teamspace = menu(teamspace=teamspace)

    menu = StudiosMenu(resolved_teamspace, vm=vm)
    studio = menu(studio=name)

    resolved_machine = Machine.from_str(machine)

    studio.__class__.show_progress = True
    studio.switch_machine(resolved_machine, interruptible=interruptible)

    save_studio_to_config(studio)

    click.echo(f"{studio._cls_name} {studio_name_link(studio)} switched to machine '{resolved_machine}' successfully")
