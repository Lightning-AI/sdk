import os
from pathlib import Path

from rich.console import Console

from lightning_sdk.api.utils import _get_cloud_url
from lightning_sdk.cli.utils.filesystem import parse_teamspace_uploads_path, resolve_teamspace


def cp_upload(
    local_file_path: str,
    teamspace_path: str,
    options: dict[str, any],
) -> None:
    console = Console()
    recursive = options.get("recursive", False)
    cloud_account = options.get("cloud_account", None)
    if not Path(local_file_path).exists():
        raise FileNotFoundError(f"The provided path does not exist: {local_file_path}")

    teamspace_path_result = parse_teamspace_uploads_path(teamspace_path)

    selected_teamspace = resolve_teamspace(teamspace_path_result["teamspace"], teamspace_path_result["owner"])
    console.print(f"Uploading to {selected_teamspace.owner.name}/{selected_teamspace.name}")

    if Path(local_file_path).is_dir():
        if not recursive:
            raise ValueError(f"'{local_file_path}' is a directory. Use -r flag to copy directories recursively.")
        selected_teamspace.upload_folder(
            local_file_path, teamspace_path_result["destination"], cloud_account=cloud_account
        )
    else:
        if teamspace_path.endswith(("/", "\\")):
            # if destination ends with / or \, treat it as a directory
            file_name = os.path.basename(local_file_path)
            teamspace_path_result["destination"] = os.path.join(teamspace_path_result["destination"], file_name)
        selected_teamspace.upload_file(
            local_file_path, teamspace_path_result["destination"], cloud_account=cloud_account
        )

    studio_url = (
        _get_cloud_url().replace(":443", "") + "/" + selected_teamspace.owner.name + "/" + selected_teamspace.name
    )
    console.print(f"See your file at {studio_url}")


def cp_download(
    teamspace_path: str,
    local_path: str,
    options: dict[str, any],
) -> None:
    console = Console()
    teamspace_path_result = parse_teamspace_uploads_path(teamspace_path)
    recursive = options.get("recursive", False)

    selected_teamspace = resolve_teamspace(teamspace_path_result["teamspace"], teamspace_path_result["owner"])

    # check if file/folder exists
    path_info = selected_teamspace._teamspace_api.get_path_info(
        selected_teamspace._teamspace.id, path=teamspace_path_result["destination"]
    )
    if not path_info["exists"]:
        raise FileNotFoundError(
            f"The provided path does not exist in the teamspace drive: {teamspace_path_result['destination']} "
            "Note that empty folders may not be detected as existing."
        )

    console.print(f"Downloading from {selected_teamspace.owner.name}/{selected_teamspace.name}")
    if path_info["type"] == "directory":
        if not recursive:
            raise ValueError(
                f"'{teamspace_path_result['destination']}' is a directory. Use -r flag to copy directories recursively."
            )
        folder_name = os.path.basename(teamspace_path_result["destination"].rstrip("/"))
        if local_path in ("./", "."):
            if folder_name == "":
                folder_name = f"{selected_teamspace.name}_downloads"
            target_path = os.path.join(local_path, folder_name)
        else:
            target_path = local_path

        selected_teamspace.download_folder(teamspace_path_result["destination"], target_path)
        console.print(f"See your folder at {target_path}")
    else:
        if os.path.isdir(local_path) or local_path.endswith(("/", "\\")):
            # if local_path ends with / or \ or is a directory, treat it as a directory
            file_name = os.path.basename(teamspace_path_result["destination"])
            target_path = os.path.join(local_path, file_name)
        else:
            target_path = local_path
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        selected_teamspace.download_file(teamspace_path_result["destination"], target_path)
        console.print(f"See your file at {target_path}")
