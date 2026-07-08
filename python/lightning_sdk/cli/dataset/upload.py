"""Dataset upload command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.dataset.download import _parse_dataset_path
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.lightning_cloud.utils.dataset import upload_dataset
from lightning_sdk.utils.resolve import _resolve_teamspace


@click.command("upload", cls=LightningCommand)
@click.argument("name")
@click.option(
    "--cluster",
    "--cluster-id",
    "--cluster_id",
    "cluster_id",
    default=None,
    help="The cluster ID to upload to.",
)
@click.option(
    "--source-path",
    "--source_path",
    "source_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Local file to upload as the dataset version.",
)
def upload_dataset_cmd(
    name: str,
    cluster_id: Optional[str] = None,
    source_path: str = "",
) -> None:
    """Upload a file as a dataset version.

    NAME must be a Lightning path: <ORG>/<TEAMSPACE>/<DATASET_ID> or
    <ORG>/<TEAMSPACE>/<DATASET_ID>/<VERSION>. If no version is specified,
    the version is auto-incremented (e.g. v1 -> v2).

    Examples:

        lightning dataset upload my-org/my-teamspace/my-dataset --source-path ./data.zip

        lightning dataset upload my-org/my-teamspace/my-dataset/v3 --source-path ./data.zip
    """
    org_name, ts_name, dataset_id, version = _parse_dataset_path(name)

    from lightning_sdk.organization import Organization

    org = Organization(org_name)
    teamspace = _resolve_teamspace(ts_name, org=org, user=None)
    project_id = teamspace.id

    from lightning_sdk.lightning_cloud.utils.dataset import _resolve_dataset_version

    version = _resolve_dataset_version(project_id, dataset_id, version, for_upload=True)

    upload_dataset(
        project_id=project_id,
        dataset_id=dataset_id,
        version=version,
        file_path=source_path,
        cluster_id=cluster_id,
    )
