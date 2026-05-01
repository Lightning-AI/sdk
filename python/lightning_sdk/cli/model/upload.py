"""Model upload command."""

from typing import Optional

import click

from lightning_sdk.models import upload_model as _upload_model


@click.command("upload")
@click.argument("name")
@click.option(
    "--path",
    default=".",
    help="The path to the file or directory you want to upload. Defaults to the current directory.",
)
@click.option(
    "--cloud-account", "--cloud_account", default=None, help="The name of the cloud account to store the Model in."
)
def upload_model(name: str, path: str = ".", cloud_account: Optional[str] = None) -> None:
    """Upload a model to a teamspace."""
    _upload_model(name, path, cloud_account=cloud_account)
