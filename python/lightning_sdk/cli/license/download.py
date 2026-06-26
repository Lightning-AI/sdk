"""License download command."""

import rich_click as click

from lightning_sdk.cli.legacy.download import download_license as _download_license
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("download", cls=LightningCommand)
@click.argument("name")
def download_license(name: str) -> None:
    """Download license for specific products/packages."""
    _download_license.callback(name=name)
