"""Studio delete command."""

from typing import Optional

import click

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
    try:
        studio = Studio(studio_name, teamspace=teamspace, create_ok=False)
        studio.delete()
    except Exception:
        # TODO: make this a generic CLI error
        if studio_name:
            raise ValueError(f"Could not delete Studio: '{studio_name}'. Does the Studio exist?") from None
        raise ValueError("No studio name provided. Use 'lightning studio delete <name>' to delete a studio.") from None

    click.echo(f"Studio '{studio.name}' deleted successfully")
