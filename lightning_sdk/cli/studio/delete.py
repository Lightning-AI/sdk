"""Studio delete command."""

from typing import Optional

import click

from lightning_sdk.cli.utils.save_to_config import save_teamspace_to_config
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.studio import Studio


@click.command("delete")
@click.argument("studio_name", required=False)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
def delete_studio(studio_name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Delete a Studio.

    Example:
      lightning studio delete [STUDIO_NAME]

    STUDIO_NAME: the name of the studio to delete.

    If STUDIO_NAME is not provided, will try to infer from environment or use the default value from the config.
    """
    # missing studio_name and teamspace are handled by the studio class
    menu = TeamspacesMenu()
    resolved_teamspace = menu(teamspace=teamspace)
    save_teamspace_to_config(resolved_teamspace, overwrite=False)

    try:
        studio = Studio(studio_name, teamspace=resolved_teamspace, create_ok=False)
        studio.delete()
    except Exception:
        # TODO: make this a generic CLI error
        if studio_name:
            raise ValueError(f"Could not delete Studio: '{studio_name}'. Does the Studio exist?") from None
        raise ValueError("No studio name provided. Use 'lightning studio delete <name>' to delete a studio.") from None

    click.echo(f"Studio '{studio.name}' deleted successfully")
