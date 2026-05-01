"""Studio cp command."""

import os
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from lightning_sdk.api.utils import _get_cloud_url
from lightning_sdk.cli.utils.filesystem import parse_studio_path, resolve_studio


@click.command("cp")
@click.argument("source", nargs=1)
@click.argument("destination", nargs=1)
@click.option("-r", "--recursive", is_flag=True, help="Copy directories recursively")
def cp_studio_file(source: str, destination: str, teamspace: Optional[str] = None, recursive: bool = False) -> None:
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
    elif "lit://" not in source and "lit://" not in destination:
        raise ValueError("Either source or destination must be a Studio file.")
    elif "lit://" in source:
        # Download from Studio to local
        cp_download(studio_path=source, local_path=destination, recursive=recursive)
    else:
        # Upload from local to Studio
        cp_upload(local_file_path=source, studio_file_path=destination, recursive=recursive)


def cp_upload(
    local_file_path: str,
    studio_file_path: str,
    recursive: bool = False,
) -> None:
    console = Console()
    if not Path(local_file_path).exists():
        raise FileNotFoundError(f"The provided path does not exist: {local_file_path}")

    studio_path_result = parse_studio_path(studio_file_path)

    selected_studio = resolve_studio(
        studio_path_result["studio"], studio_path_result["teamspace"], studio_path_result["owner"]
    )
    console.print(f"Uploading to {selected_studio.teamspace.name}/{selected_studio.name}")

    if Path(local_file_path).is_dir():
        if not recursive:
            raise ValueError(f"'{local_file_path}' is a directory. Use -r flag to copy directories recursively.")
        selected_studio.upload_folder(local_file_path, studio_path_result["destination"])
    else:
        if studio_file_path.endswith(("/", "\\")):
            # if destination ends with / or \, treat it as a directory
            file_name = os.path.basename(local_file_path)
            studio_path_result["destination"] = os.path.join(studio_path_result["destination"], file_name)
        selected_studio.upload_file(local_file_path, studio_path_result["destination"])

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
    studio_path: str,
    local_path: str,
    recursive: bool = False,
) -> None:
    console = Console()
    studio_path_result = parse_studio_path(studio_path)

    selected_studio = resolve_studio(
        studio_path_result["studio"], studio_path_result["teamspace"], studio_path_result["owner"]
    )

    # check if file/folder exists
    path_info = selected_studio._studio_api.get_path_info(
        selected_studio._studio.id, selected_studio._teamspace.id, path=studio_path_result["destination"]
    )
    if not path_info["exists"]:
        raise FileNotFoundError(
            f"The provided path does not exist in the studio: {studio_path_result['destination']} "
            "Note that empty folders may not be detected as existing."
        )

    console.print(f"Downloading from {selected_studio.teamspace.name}/{selected_studio.name}")
    if path_info["type"] == "directory":
        if not recursive:
            raise ValueError(
                f"'{studio_path_result['destination']}' is a directory. Use -r flag to copy directories recursively."
            )
        folder_name = os.path.basename(studio_path_result["destination"].rstrip("/"))
        if local_path in ("./", "."):
            if folder_name == "":
                # handle root directory case (e.g. lit://lightning-ai/gpt-oss/studios/manual-lime-ylu2/)
                folder_name = selected_studio.name
            target_path = os.path.join(local_path, folder_name)
        else:
            target_path = local_path

        selected_studio.download_folder(studio_path_result["destination"], target_path)
        console.print(f"See your folder at {target_path}")
    else:
        if os.path.isdir(local_path) or local_path.endswith(("/", "\\")):
            # if local_path ends with / or \ or is a directory, treat it as a directory
            file_name = os.path.basename(studio_path_result["destination"])
            target_path = os.path.join(local_path, file_name)
        else:
            target_path = local_path
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        selected_studio.download_file(studio_path_result["destination"], target_path)
        console.print(f"See your file at {target_path}")
