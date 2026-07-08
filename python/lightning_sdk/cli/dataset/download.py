"""Dataset download command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.lightning_cloud.utils.dataset import _download_dataset_version
from lightning_sdk.utils.resolve import _resolve_teamspace


def _parse_dataset_path(name: str) -> tuple:
    """Parse a dataset path like 'org/teamspace/dataset/version' into components.

    Returns (org, teamspace_name, dataset_id, version).
    """
    parts = name.split("/")
    if len(parts) == 3:
        # org/teamspace/dataset_id (no version specified)
        org_name, ts_name, dataset_id = parts
        version = None
    elif len(parts) >= 4:
        org_name, ts_name, dataset_id, *rest = parts
        version = rest[0] if rest else None
    else:
        raise click.UsageError(
            "NAME must be a Lightning path in the format <ORG>/<TEAMSPACE>/<DATASET_ID> "
            "or <ORG>/<TEAMSPACE>/<DATASET_ID>/<VERSION>, "
            "e.g. 'my-org/my-teamspace/my-dataset' or 'my-org/my-teamspace/my-dataset/v3'"
        )

    if not org_name or not ts_name or not dataset_id:
        raise click.UsageError(
            "NAME must be a Lightning path in the format <ORG>/<TEAMSPACE>/<DATASET_ID> "
            "or <ORG>/<TEAMSPACE>/<DATASET_ID>/<VERSION>, "
            "e.g. 'my-org/my-teamspace/my-dataset' or 'my-org/my-teamspace/my-dataset/v3'"
        )

    return org_name, ts_name, dataset_id, version


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
def download_dataset(
    name: str,
    cluster_id: Optional[str] = None,
    target_path: str = ".",
) -> None:
    """Download a dataset version as a zip file.

    NAME must be a Lightning path: <ORG>/<TEAMSPACE>/<DATASET_ID> or
    <ORG>/<TEAMSPACE>/<DATASET_ID>/<VERSION>. If no version is specified,
    the most recent version is used.

    Examples:

        lightning dataset download my-org/my-teamspace/my-dataset

        lightning dataset download my-org/my-teamspace/my-dataset/v3

        lightning dataset download my-org/my-teamspace/my-dataset/v3 --target-path ./data
    """
    org_name, ts_name, dataset_id, version = _parse_dataset_path(name)

    from lightning_sdk.organization import Organization

    org = Organization(org_name)
    teamspace = _resolve_teamspace(ts_name, org=org, user=None)
    project_id = teamspace.id

    from lightning_sdk.lightning_cloud.utils.dataset import _resolve_dataset_version

    version = _resolve_dataset_version(project_id, dataset_id, version)

    import os

    zip_path = os.path.join(target_path, f"{dataset_id}_{version}.zip")
    _download_dataset_version(
        project_id=project_id,
        dataset_id=dataset_id,
        version=version,
        target_path=zip_path,
        cluster_id=cluster_id,
    )
    click.echo(f"Downloaded dataset '{dataset_id}' version '{version}' to {zip_path}")
