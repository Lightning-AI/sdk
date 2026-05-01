"""Studio delete command."""

from typing import Optional

import click

from lightning_sdk.cli.utils.studio_selection import StudiosMenu
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu


@click.command("delete")
@click.option(
    "--name",
    help=(
        "The name of the studio to delete. "
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
    return delete_impl(name=name, teamspace=teamspace, vm=False)


def delete_impl(name: Optional[str], teamspace: Optional[str], vm: bool) -> None:
    menu = TeamspacesMenu()
    resolved_teamspace = menu(teamspace=teamspace)

    menu = StudiosMenu(resolved_teamspace, vm=vm)
    studio = menu(studio=name)

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
