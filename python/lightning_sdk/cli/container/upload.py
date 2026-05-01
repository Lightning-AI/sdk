"""Container upload command."""

from typing import Optional

import click

from lightning_sdk.cli.legacy.upload import upload_container as _upload_container


@click.command("upload")
@click.argument("container")
@click.option("--tag", default="latest", help="The tag of the container to upload.")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "The teamspace the studio is part of. "
        "Should be of format <OWNER>/<TEAMSPACE_NAME>. "
        "If not specified, tries to infer from the environment (e.g. when run from within a Studio.)"
    ),
)
@click.option(
    "--cloud-account",
    "--cloud_account",
    default=None,
    help="The name of the cloud account to store the Container in.",
)
@click.option(
    "--platform",
    default="linux/amd64",
    help="This is the platform the container pulled and push to Lightning AI will run on.",
)
def upload_container(
    container: str,
    tag: str = "latest",
    teamspace: Optional[str] = None,
    cloud_account: Optional[str] = None,
    platform: Optional[str] = "linux/amd64",
) -> None:
    """Upload a container to Lightning AI's container registry."""
    _upload_container.callback(
        container=container,
        tag=tag,
        teamspace=teamspace,
        cloud_account=cloud_account,
        platform=platform,
    )
