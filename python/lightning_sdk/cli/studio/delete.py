"""Studio delete command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_studio, resolve_teamspace


@click.command("delete", cls=LightningCommand)
@click.option(
    "--name",
    help="Studio to use. Falls back to the current Studio or configured default.",
)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
def delete_studio(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Delete a Studio.

    Example:
      lightning studio delete --name my-studio

    """
    return delete_impl(name=name, teamspace=teamspace)


def delete_impl(name: Optional[str], teamspace: Optional[str]) -> None:
    resolved_teamspace = resolve_teamspace(teamspace)
    studio = resolve_studio(name, resolved_teamspace)

    studio_name = f"{studio.teamspace.owner.name}/{studio.teamspace.name}/{studio.name}"
    confirmed = click.confirm(
        f"Are you sure you want to delete {studio._cls_name} '{studio_name}'?",
        abort=True,
    )
    if not confirmed:
        click.echo(f"{studio._cls_name} deletion cancelled")
        return

    studio.delete()

    click.echo(f"{studio._cls_name} '{studio.name}' deleted successfully")
