"""Dataset download command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.datasets import download_dataset


@click.command("download", cls=LightningCommand)
@click.argument("name")
@click.option(
    "--cluster",
    "--cluster-id",
    "--cluster_id",
    "cluster_id",
    default=None,
    help="The cluster ID to download from.",
)
@click.option(
    "--target-path",
    "--target_path",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Local directory to download the dataset zip into.",
)
def download_dataset_cmd(
    name: str,
    cluster_id: Optional[str] = None,
    target_path: str = ".",
) -> None:
    """Download a dataset version as a zip file.

    NAME must be a Lightning path: <ORG>/<TEAMSPACE>/<DATASET_NAME> or
    <ORG>/<TEAMSPACE>/<DATASET_NAME>/<VERSION>. If no version specified,
    defaults to most recent version.

    Usage:
        lightning dataset download my-org/my-teamspace/my-dataset
        lightning dataset download my-org/my-teamspace/my-dataset/v3
        lightning dataset download my-org/my-teamspace/my-dataset/v3 --target-path ./data
    """
    info = download_dataset(
        name=name,
        target_path=target_path,
        cluster_id=cluster_id,
    )
    click.echo(f"Downloaded dataset '{info.name}' version '{info.version}' to {info.path}")
