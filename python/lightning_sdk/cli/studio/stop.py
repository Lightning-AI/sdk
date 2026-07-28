"""Studio stop command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_studio, resolve_teamspace
from lightning_sdk.cli.utils.richt_print import studio_name_link
from lightning_sdk.cli.utils.save_to_config import save_studio_to_config


@click.command("stop", cls=LightningCommand)
@click.option(
    "--name",
    help="Studio to use. Falls back to the current Studio or configured default.",
)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
def stop_studio(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Stop a Studio.

    Example:
        lightning studio stop --name my-studio

    """
    return stop_impl(name=name, teamspace=teamspace)


def stop_impl(name: Optional[str], teamspace: Optional[str]) -> None:
    resolved_teamspace = resolve_teamspace(teamspace)
    studio = resolve_studio(name, resolved_teamspace)

    studio.stop()

    save_studio_to_config(studio)

    click.echo(f"{studio._cls_name} {studio_name_link(studio)} stopped successfully")
