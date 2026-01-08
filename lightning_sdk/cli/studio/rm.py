"""Studio rm command."""

import click
from rich.console import Console

from lightning_sdk.cli.utils.studio_filesystem import parse_studio_path, resolve_studio
from lightning_sdk.studio import Studio


@click.command("rm")
@click.argument("path", nargs=1)
@click.option("-r", "--recursive", is_flag=True, help="Remove directories recursively")
@click.option("-f", "--force", is_flag=True, help="Ignore nonexistent files, never prompt")
def rm_studio_file(path: str, recursive: bool = False, force: bool = False) -> None:
    """Remove a Studio file or directory.

    PATH: Studio path to remove. Use the format lit://<owner>/<my-teamspace>/studios/<my-studio>/<filepath>.

    Example:
        lightning studio rm lit://<owner>/<my-teamspace>/studios/<my-studio>/file.txt
        lightning studio rm -r lit://<owner>/<my-teamspace>/studios/<my-studio>/folder/

    """
    return rm_impl(path=path, recursive=recursive, force=force)


def rm_impl(path: str, recursive: bool = False, force: bool = False) -> None:
    if "lit://" not in path:
        raise ValueError("Path must be a Studio path starting with 'lit://'.")

    console = Console()
    studio_path_result = parse_studio_path(path)

    selected_studio = resolve_studio(
        studio_path_result["studio"], studio_path_result["teamspace"], studio_path_result["owner"]
    )

    # check if file/folder exists
    path_info = selected_studio._studio_api.get_path_info(
        selected_studio._studio.id, selected_studio._teamspace.id, path=studio_path_result["destination"]
    )

    if not path_info["exists"]:
        if force:
            # silently ignore nonexistent files with -f flag
            return
        raise FileNotFoundError(
            f"The provided path does not exist in the studio: '{studio_path_result['destination']}'. "
            "Note that empty folders may not be detected as existing."
        )

    console.print(f"Removing from {selected_studio.teamspace.name}/{selected_studio.name}")

    if path_info["type"] == "directory":
        if not recursive:
            raise ValueError(
                f"'{studio_path_result['destination']}' is a directory. Use -r flag to remove directories recursively."
            )
        rm_folder(selected_studio=selected_studio, path=studio_path_result["destination"], console=console)
    else:
        rm_file(selected_studio=selected_studio, path=studio_path_result["destination"], console=console)


def rm_file(selected_studio: Studio, path: str, console: Console) -> None:
    selected_studio._studio_api.remove_file(selected_studio._studio.id, selected_studio._teamspace.id, path)
    console.print(f"Removed file: {path}")


def rm_folder(selected_studio: Studio, path: str, console: Console) -> None:
    selected_studio._studio_api.remove_folder(selected_studio._studio.id, selected_studio._teamspace.id, path)
    console.print(f"Removed directory: {path}")
