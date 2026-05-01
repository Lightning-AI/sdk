"""License download-all command."""

import click

from lightning_sdk.cli.legacy.download import download_licenses as _download_licenses


@click.command("download-all")
def download_licenses() -> None:
    """Download licenses for all user's products/packages."""
    _download_licenses.callback()
