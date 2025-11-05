"""Studio cp command."""

from pathlib import Path
from typing import Optional, TypedDict

import click
from rich.console import Console

from lightning_sdk.api.utils import _get_cloud_url
from lightning_sdk.cli.legacy.exceptions import StudioCliError
from lightning_sdk.cli.utils.owner_selection import OwnerMenu
from lightning_sdk.cli.utils.studio_selection import StudiosMenu
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.studio import Studio


@click.command("cp")
@click.argument("source", nargs=1)
@click.argument("destination", nargs=1)
def cp_studio_file(source: str, destination: str, teamspace: Optional[str] = None) -> None:
    """Copy a Studio file.

    SOURCE: Source file to copy from. For Studio files, use the format lit://<owner>/<my-teamspace>/studios/<my-studio>/<filepath>.

    DESTINATION: Destination file to copy to. For Studio files, use the format lit://<owner>/<my-teamspace>/studios/<my-studio>/<filepath>.

    Example:
        lightning studio cp source.txt lit://<owner>/<my-teamspace>/studios/<my-studio>/destination.txt

    """
    return cp_impl(source=source, destination=destination)


def cp_impl(source: str, destination: str) -> None:
    if "lit://" in source and "lit://" in destination:
        raise ValueError("Both source and destination cannot be Studio files.")
    elif "lit://" not in source and "lit://" not in destination:
        raise ValueError("Either source or destination must be a Studio file.")
    elif "lit://" in source:
        # Download from Studio to local
        cp_download(studio_file_path=source, local_file_path=destination)
    else:
        # Upload from local to Studio
        cp_upload(local_file_path=source, studio_file_path=destination)


class StudioPathResult(TypedDict):
    owner: Optional[str]
    teamspace: Optional[str]
    studio: Optional[str]
    destination: Optional[str]


def parse_studio_path(studio_path: str) -> StudioPathResult:
    path_string = studio_path.removeprefix("lit://")
    if not path_string:
        raise ValueError("Studio path cannot be empty after prefix")

    result: StudioPathResult = {"owner": None, "teamspace": None, "studio": None, "destination": None}

    if "/studios/" in path_string:
        prefix_part, suffix_part = path_string.split("/studios/", 1)

        # org and teamspace
        if prefix_part:
            org_ts_components = prefix_part.split("/")
            if len(org_ts_components) == 2:
                result["owner"], result["teamspace"] = org_ts_components
            elif len(org_ts_components) == 1:
                result["teamspace"] = org_ts_components[0]
            else:
                raise ValueError(f"Invalid format: '{prefix_part}'")

        # studio and destination
        path_parts = suffix_part.split("/")

    else:
        # studio and destination
        path_parts = path_string.split("/")

    if not path_parts or len(path_parts) < 2:
        raise ValueError("Invalid: Missing studio name.")

    result["studio"] = path_parts[0]
    result["destination"] = "/".join(path_parts[1:])

    return result


def cp_upload(
    local_file_path: str,
    studio_file_path: str,
) -> None:
    console = Console()
    if Path(local_file_path).is_dir():
        raise StudioCliError(
            f"The provided path is a folder: {local_file_path}. Use `lightning upload folder` instead."
        )
    if not Path(local_file_path).exists():
        raise FileNotFoundError(f"The provided path does not exist: {local_file_path}.")

    studio_path_result = parse_studio_path(studio_file_path)

    selected_studio = resolve_studio(
        studio_path_result["studio"], studio_path_result["teamspace"], studio_path_result["owner"]
    )
    console.print(f"Uploading to {selected_studio.teamspace.name}/{selected_studio.name}")

    selected_studio.upload_file(local_file_path, studio_file_path)

    studio_url = (
        _get_cloud_url().replace(":443", "")
        + "/"
        + selected_studio.owner.name
        + "/"
        + selected_studio.teamspace.name
        + "/studios/"
        + selected_studio.name
    )
    console.print(f"See your file at {studio_url}")


def cp_download(
    studio_file_path: str,
    local_file_path: str,
) -> None:
    raise NotImplementedError("Download functionality is not implemented yet.")


def resolve_studio(studio_name: Optional[str], teamspace: Optional[str], owner: Optional[str]) -> Studio:
    owner_menu = OwnerMenu()
    resolved_owner = owner_menu(owner=owner)

    teamspace_menu = TeamspacesMenu(resolved_owner)
    resolved_teamspace = teamspace_menu(teamspace=teamspace)

    studio_menu = StudiosMenu(resolved_teamspace)
    return studio_menu(studio=studio_name)
