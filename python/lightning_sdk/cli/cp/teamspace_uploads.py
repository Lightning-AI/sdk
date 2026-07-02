import os
from pathlib import Path

from rich.console import Console

from lightning_sdk.api.utils import _get_cloud_url
from lightning_sdk.cli.utils.filesystem import parse_teamspace_uploads_path, path_join, resolve_teamspace


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

    teamspace_path_result["destination"] = path_join("Uploads", teamspace_path_result["destination"])

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
            teamspace_path_result["destination"] = path_join(teamspace_path_result["destination"], file_name)
        selected_teamspace.upload_file(
            local_file_path, teamspace_path_result["destination"], cloud_account=cloud_account
        )

    studio_url = (
        _get_cloud_url().replace(":443", "") + "/" + selected_teamspace.owner.name + "/" + selected_teamspace.name
    )
    console.print(f"See your file at {studio_url}")
