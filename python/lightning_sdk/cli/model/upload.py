"""Model upload command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.models import upload_model as _upload_model


@click.command("upload", cls=LightningCommand)
@click.argument("name", metavar="ORG-NAME/TEAMSPACE-NAME/MODEL-NAME")
@click.option(
    "--path",
    required=True,
    help="The path to the file or directory you want to upload.",
)
@click.option(
    "--cloud-account", "--cloud_account", default=None, help="The name of the cloud account to store the Model in."
)
def upload_model(name: str, path: str, cloud_account: Optional[str] = None) -> None:
    """Upload a model to a teamspace."""
    _upload_model(name, path, cloud_account=cloud_account)