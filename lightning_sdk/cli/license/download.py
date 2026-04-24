"""License download command."""

import click

from lightning_sdk.cli.legacy.download import download_license as _download_license


@click.command("download")
@click.argument("name")
def download_license(name: str) -> None:
    """Download license for specific products/packages."""
    _download_license.callback(name=name)
