"""Container download command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.legacy.download import download_container as _download_container
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("download", cls=LightningCommand)
@click.argument("container")
@click.option("--teamspace", default=None, help="The name of the teamspace to download the container from")
@click.option("--tag", default="latest", show_default=True, help="The tag of the container to download.")
@click.option(
    "--cloud-account",
    "--cloud_account",
    default=None,
    help="The name of the cloud account to download the Container from.",
)
def download_container(
    container: str, teamspace: Optional[str] = None, tag: str = "latest", cloud_account: Optional[str] = None
) -> None:
    """Download a docker container from a teamspace."""
    _download_container.callback(container=container, teamspace=teamspace, tag=tag, cloud_account=cloud_account)
