"""Studio cp command."""

from typing import Tuple

import rich_click as click
from rich.console import Console

from lightning_sdk.api.utils import _get_cloud_url
from lightning_sdk.cli.utils.filesystem import parse_studio_path, resolve_studio
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.filesystem import Filesystem
from lightning_sdk.studio import Studio


@click.command("cp", cls=LightningCommand)
@click.argument("source", nargs=1)
@click.argument("destination", nargs=1)
@click.option("-r", "--recursive", is_flag=True, help="Copy directories recursively")
def cp_studio_file(source: str, destination: str, recursive: bool = False) -> None:
    """Copy a Studio file.

    SOURCE: Source file to copy from. For Studio files, use the format lit://<owner>/<my-teamspace>/studios/<my-studio>/<filepath>.

    DESTINATION: Destination file to copy to. For Studio files, use the format lit://<owner>/<my-teamspace>/studios/<my-studio>/<filepath>.

    Example:
        lightning studio cp source.txt lit://<owner>/<my-teamspace>/studios/<my-studio>/destination.txt
        lightning studio cp -r source_folder/ lit://<owner>/<my-teamspace>/studios/<my-studio>/destination_folder/

    """
    return cp_impl(source=source, destination=destination, recursive=recursive)


def cp_impl(source: str, destination: str, recursive: bool = False) -> None:
    if "lit://" in source and "lit://" in destination:
        raise ValueError("Both source and destination cannot be Studio files.")
    if "lit://" not in source and "lit://" not in destination:
        raise ValueError("Either source or destination must be a Studio file.")

    is_download = "lit://" in source
    console = Console()
    studio, drive_url = _resolve_drive_url(source if is_download else destination)

    if is_download:
        console.print(f"Downloading from {studio.teamspace.name}/{studio.name}")
        Filesystem().copy(source=drive_url, destination=destination, recursive=recursive)
        return

    console.print(f"Uploading to {studio.teamspace.name}/{studio.name}")
    Filesystem().copy(source=source, destination=drive_url, recursive=recursive)

    studio_url = (
        _get_cloud_url().replace(":443", "") + f"/{studio.owner.name}/{studio.teamspace.name}/studios/{studio.name}"
    )
    console.print(f"See your file at {studio_url}")


def _resolve_drive_url(studio_path: str) -> Tuple[Studio, str]:
    """Resolve a studio lit URL to the studio and its fully-qualified drive URL.

    Unlike the main ``lightning cp`` URLs, studio paths may omit the owner or
    the owner and teamspace, which then resolve from the configured defaults.
    """
    parsed = parse_studio_path(studio_path)
    studio = resolve_studio(parsed["studio"], parsed["teamspace"], parsed["owner"])
    destination = parsed["destination"] or ""
    return studio, f"lit://{studio.owner.name}/{studio.teamspace.name}/studios/{studio.name}/{destination}"
