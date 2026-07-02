"""License download-all command."""

import rich_click as click

from lightning_sdk.cli.legacy.download import download_licenses as _download_licenses
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("download-all", cls=LightningCommand)
def download_licenses() -> None:
    """Download licenses for all user's products/packages."""
    _download_licenses.callback()
