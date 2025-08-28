"""Studio stop command."""

from typing import Optional

import click

from lightning_sdk.cli.utils.richt_print import studio_name_link
from lightning_sdk.cli.utils.save_to_config import save_studio_to_config
from lightning_sdk.cli.utils.studio_selection import StudiosMenu
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu


@click.command("stop")
@click.option(
    "--name",
    help=(
        "The name of the studio to start. "
        "If not provided, will try to infer from environment, "
        "use the default value from the config or prompt for interactive selection."
    ),
)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
def stop_studio(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Stop a Studio.

    Example:
        lightning studio stop --name my-studio

    """
    # missing studio_name and teamspace are handled by the studio class
    menu = TeamspacesMenu()
    resolved_teamspace = menu(teamspace=teamspace)

    menu = StudiosMenu(resolved_teamspace)
    studio = menu(studio=name)

    studio.stop()

    save_studio_to_config(studio)

    click.echo(f"Studio {studio_name_link(studio)} stopped successfully")
