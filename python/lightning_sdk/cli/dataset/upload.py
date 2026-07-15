"""Dataset upload command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.datasets import upload_dataset


@click.command("upload", cls=LightningCommand)
@click.argument("name")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option(
    "--cloud-account",
    "--cloud_account",
    "cloud_account",
    default=None,
    help="Cloud account ID to store the dataset files in. Falls back to the teamspace default.",
)
def upload_dataset_cmd(
    name: str,
    path: str = ".",
    cloud_account: Optional[str] = None,
) -> None:
    """Upload a dataset to Lightning Datasets.

    NAME must be a Lightning path: <ORG>/<TEAMSPACE>/<DATASET-NAME> or
    <ORG>/<TEAMSPACE>/<DATASET-NAME>/<VERSION>.

    PATH is a local file or directory to upload (defaults to current directory).

    Usage:
        lightning dataset upload my-org/my-teamspace/my-dataset ./data
        lightning dataset upload my-org/my-teamspace/my-dataset/v1 ./data
        lightning dataset upload my-org/my-teamspace/my-dataset ./data --cloud-account my-aws-account
    """
    result = upload_dataset(
        name=name,
        path=path,
        cloud_account=cloud_account,
    )

    click.echo(f"Uploaded dataset '{result.name}' version '{result.version}' to teamspace '{result.teamspace}'")
