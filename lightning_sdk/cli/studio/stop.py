"""Studio stop command."""

from typing import Optional

import click

from lightning_sdk.studio import Studio


@click.command("stop")
@click.argument("studio_name", required=False)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
def stop_studio(studio_name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Stop a Studio.

    Example:
        lightning studio stop [STUDIO_NAME]

    STUDIO_NAME: the name of the studio to stop.

    If STUDIO_NAME is not provided, will try to infer from environment or use the default value from the config.
    """
    # missing studio_name and teamspace are handled by the studio class
    try:
        studio = Studio(studio_name, teamspace=teamspace)
        studio.stop()
    except Exception:
        # TODO: make this a generic CLI error
        if studio_name:
            raise ValueError(f"Could not stop studio: '{studio_name}'. Does the studio exist?") from None
        raise ValueError("No studio name provided. Use 'lightning studio stop <name>' to stop a studio.") from None

    click.echo(f"Studio '{studio.name}' stopped successfully")
