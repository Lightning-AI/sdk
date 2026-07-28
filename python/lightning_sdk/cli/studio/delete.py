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
@click.option("--yes", "-y", is_flag=True, default=False, help="Confirm deletion without prompting.")
def delete_studio(
    name: Optional[str] = None,
    teamspace: Optional[str] = None,
    yes: bool = False,
) -> None:
    """Delete a Studio.

    Example:
      lightning studio delete --name my-studio

    """
    return delete_impl(name=name, teamspace=teamspace, yes=yes)


def delete_impl(name: Optional[str], teamspace: Optional[str], yes: bool) -> None:
    if not yes:
        raise click.UsageError("Deleting a studio requires --yes.")

    resolved_teamspace = resolve_teamspace(teamspace)
    studio = resolve_studio(name, resolved_teamspace)

    studio.delete()

    click.echo(f"{studio._cls_name} '{studio.name}' deleted successfully")
