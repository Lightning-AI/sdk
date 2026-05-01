"""Model download command."""

import click

from lightning_sdk.models import download_model


@click.command("download")
@click.argument("name")
@click.option(
    "--download-dir", "--download_dir", default=".", help="The directory where the Model should be downloaded."
)
def download_model_cmd(name: str, download_dir: str = ".") -> None:
    """Download a model from a teamspace."""
    download_model(name=name, download_dir=download_dir, progress_bar=True)
