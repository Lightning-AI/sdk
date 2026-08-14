"""Studio switch command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.resource_completion import complete_studio
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_studio, resolve_teamspace
from lightning_sdk.cli.utils.richt_print import studio_name_link
from lightning_sdk.cli.utils.save_to_config import save_studio_to_config
from lightning_sdk.machine import Machine


@click.command("switch", cls=LightningCommand)
@click.option(
    "--name",
    help="Studio to use. Falls back to the current Studio or configured default.",
    shell_complete=complete_studio,
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
    )


def switch_impl(
    name: Optional[str],
    teamspace: Optional[str],
    machine: Optional[str],
    interruptible: bool,
) -> None:
    resolved_teamspace = resolve_teamspace(teamspace)
    studio = resolve_studio(name, resolved_teamspace)

    if machine is None:
        raise click.UsageError("--machine is required.")
    resolved_machine = Machine.from_str(machine)

    studio.__class__.show_progress = True
    studio.switch_machine(resolved_machine, interruptible=interruptible)

    save_studio_to_config(studio)

    click.echo(f"{studio._cls_name} {studio_name_link(studio)} switched to machine '{resolved_machine}' successfully")
