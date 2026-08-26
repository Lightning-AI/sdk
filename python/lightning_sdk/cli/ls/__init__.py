"""ls CLI command."""

import rich_click as click

from lightning_sdk.api.filesystem_api import FilesystemApi
from lightning_sdk.api.utils import _tree_path_info
from lightning_sdk.cli.cp.completion import complete_remote_path
from lightning_sdk.cli.utils.filesystem import resolve_lit_url
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("ls", cls=LightningCommand)
@click.argument("path", nargs=1, shell_complete=complete_remote_path)
@click.option("-r", "--recursive", is_flag=True, help="List files in all subdirectories recursively")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output the listing entries as JSON.")
def ls(path: str, recursive: bool = False, as_json: bool = False) -> None:
    """List contents of a teamspace drive directory.

    PATH: Drive path in the format lit://<owner>/<teamspace>/<directory-path>,
    or lit:///<directory-path> for the current teamspace.
    The teamspace root lists the drive's top-level folders (studios, uploads, ...).

    Examples:
        lightning ls lit://<owner>/<my-teamspace>/
        lightning ls lit://<owner>/<my-teamspace>/artifacts/reports
        lightning ls lit:///artifacts/reports
        lightning ls -r lit://<owner>/<my-teamspace>/artifacts/reports
        lightning ls --json lit://<owner>/<my-teamspace>/artifacts/reports

    """
    return ls_impl(path=path, recursive=recursive, as_json=as_json)


def ls_impl(path: str, recursive: bool = False, as_json: bool = False) -> None:
    if not path.startswith("lit://"):
        raise ValueError("Path must be a drive path starting with 'lit://'.")

    selected_teamspace, remote_path = resolve_lit_url(path)
    remote_path = remote_path.strip("/")

    filesystem_api = FilesystemApi()

    def list_entries(folder: str) -> list:
        return filesystem_api.list_files(teamspace_id=selected_teamspace.id, path=folder, recursive=False)

    path_info = _tree_path_info(list_entries, remote_path)
    if not path_info["exists"]:
        raise FileNotFoundError(
            f"The provided path does not exist in the teamspace drive: {remote_path!r}. "
            "Note that empty folders may not be detected as existing."
        )

    if path_info["type"] == "file":
        if as_json:
            parent_path, _, target_name = remote_path.rpartition("/")
            echo_json([entry for entry in list_entries(parent_path) if entry.get("path") == target_name])
            return
        # print the file name if it's a file (bash-like behavior)
        print(remote_path)
        return

    entries = filesystem_api.list_files(teamspace_id=selected_teamspace.id, path=remote_path, recursive=recursive)
    if as_json:
        echo_json(entries)
        return

    for entry in entries:
        name = entry.get("path", "")
        if entry.get("type") == "tree":
            name += "/"
        print(name)
