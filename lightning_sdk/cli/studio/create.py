"""Studio start command."""

from typing import Optional

import click

from lightning_sdk.cli.utils.resolve import resolve_teamspace_owner_name_format
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.machine import CloudProvider
from lightning_sdk.studio import Studio


@click.command("create")
@click.argument("studio_name", required=False)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
@click.option(
    "--cloud-provider",
    help="The cloud provider to start the studio on. Defaults to teamspace default.",
    type=click.Choice(m.name for m in list(CloudProvider)),
)
@click.option(
    "--cloud-account",
    help="The cloud account to create the studio on. Defaults to teamspace default.",
    type=click.STRING,
)
def create_studio(
    studio_name: Optional[str] = None,
    teamspace: Optional[str] = None,
    cloud_provider: Optional[str] = None,
    cloud_account: Optional[str] = None,
) -> None:
    """Create a new Studio.

    Example:
        lightning studio create [STUDIO_NAME]

    STUDIO_NAME: the name of the studio to create.

    If STUDIO_NAME is not provided, will try to infer from environment or use the default value from the config.
    """
    if teamspace is not None:
        resolved_teamspace = resolve_teamspace_owner_name_format(teamspace)
        if resolved_teamspace is None:
            raise ValueError(
                f"Could not resolve teamspace: '{teamspace}'. Teamspace should be specified as 'owner/name'. "
                "Does the teamspace exist?"
            )
    else:
        resolved_teamspace = None

    if cloud_provider is not None:
        cloud_provider = CloudProvider(cloud_provider)

    try:
        studio = Studio(
            studio_name,
            teamspace=resolved_teamspace,
            create_ok=True,
            cloud_provider=cloud_provider,
            cloud_account=cloud_account,
        )
    except (RuntimeError, ValueError, ApiException) as e:
        print(e)
        if studio_name:
            raise ValueError(f"Could not create Studio: '{studio_name}'. Does the Studio exist?") from None
        raise ValueError(f"Could not create Studio: '{studio_name}'. Please provide a Studio name") from None

    click.echo(f"Studio '{studio.name}' created successfully")
