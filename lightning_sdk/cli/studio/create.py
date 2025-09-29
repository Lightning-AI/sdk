"""Studio start command."""

from typing import Optional

import click

from lightning_sdk.cli.utils.richt_print import studio_name_link
from lightning_sdk.cli.utils.save_to_config import save_teamspace_to_config
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.machine import CloudProvider
from lightning_sdk.studio import VM, Studio


@click.command("create")
@click.option("--name", help="The name of the studio to create. If not provided, a random name will be generated.")
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
    name: Optional[str] = None,
    teamspace: Optional[str] = None,
    cloud_provider: Optional[str] = None,
    cloud_account: Optional[str] = None,
) -> None:
    """Create a new Studio.

    Example:
        lightning studio create
    """
    create_impl(name=name, teamspace=teamspace, cloud_provider=cloud_provider, cloud_account=cloud_account, vm=False)


def create_impl(
    name: Optional[str],
    teamspace: Optional[str],
    cloud_provider: Optional[str],
    cloud_account: Optional[str],
    vm: bool,
) -> None:
    menu = TeamspacesMenu()

    resolved_teamspace = menu(teamspace)
    save_teamspace_to_config(resolved_teamspace, overwrite=False)

    if cloud_provider is not None:
        cloud_provider = CloudProvider(cloud_provider)

    create_cls = VM if vm else Studio
    cls_name = create_cls.__qualname__

    try:
        create_cls = VM if vm else Studio
        studio = create_cls(
            name=name,
            teamspace=resolved_teamspace,
            create_ok=True,
            cloud_provider=cloud_provider,
            cloud_account=cloud_account,
        )
    except (RuntimeError, ValueError, ApiException):
        if name:
            raise ValueError(f"Could not create {cls_name}: '{name}'. Does the {cls_name} exist?") from None
        raise ValueError(f"Could not create {cls_name}: '{name}'. Please provide a {cls_name} name") from None

    click.echo(f"{cls_name} {studio_name_link(studio)} created successfully")
