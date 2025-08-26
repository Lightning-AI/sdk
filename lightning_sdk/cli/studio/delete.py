"""Studio delete command."""

from typing import Optional

import click

from lightning_sdk.cli.utils.studio_selection import StudiosMenu
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu


@click.command("delete")
@click.option(
    "--name",
    help=(
        "The name of the studio to start. "
        "If not provided, will try to infer from environment, "
        "use the default value from the config or prompt for interactive selection."
    ),
)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
def delete_studio(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Delete a Studio.

    Example:
      lightning studio delete --name my-studio

    """
    menu = TeamspacesMenu()
    resolved_teamspace = menu(teamspace=teamspace)

    menu = StudiosMenu(resolved_teamspace)
    studio = menu(studio=name)

    studio_name = f"{studio.teamspace.owner.name}/{studio.teamspace.name}/{studio.name}"
    confirmed = click.confirm(
        f"Are you sure you want to delete studio '{studio_name}'?",
        abort=True,
    )
    if not confirmed:
        click.echo("Studio deletion cancelled")
        return

    studio.delete()

    click.echo(f"Studio '{studio.name}' deleted successfully")
