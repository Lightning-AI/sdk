"""Studio ls command."""

import rich_click as click

from lightning_sdk.cli.studio.paths import parse_studio_path, resolve_studio
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("ls", cls=LightningCommand)
@click.argument("path", nargs=1)
def ls_studio(path: str) -> None:
    """List contents of a directory in Studio.

    PATH: Studio path in the format
            lit://<owner>/<teamspace>/studios/<studio>/<directory-path>,
          or lit:///studios/<studio>/<directory-path> for the current teamspace.

    Example:
        lightning studio ls lit://<owner>/<my-teamspace>/studios/<my-studio>/data
        lightning studio ls lit:///studios/<my-studio>/data

    """
    return ls_impl(path=path)


def ls_impl(path: str) -> None:
    if not path.startswith("lit://"):
        raise ValueError("Path must be a Studio path starting with 'lit://'.")

    studio_path_result = parse_studio_path(path)
    destination = studio_path_result["destination"] or ""
    selected_studio = resolve_studio(
        studio_path_result["studio"], studio_path_result["teamspace"], studio_path_result["owner"]
    )

    path_info = selected_studio._studio_api.get_path_info(
        selected_studio._studio.id, selected_studio._teamspace.id, path=destination
    )

    if not path_info["exists"]:
        raise FileNotFoundError(
            f"The provided path does not exist in the studio: {studio_path_result['destination']} "
            "Note that empty folders may not be detected as existing."
        )

    if path_info["type"] == "file":
        # print the file name if it's a file (bash-like behavior)
        print(destination)
        return

    tree = selected_studio._studio_api.get_tree(
        selected_studio._studio.id, selected_studio._teamspace.id, path=destination
    )

    tree_items = tree.get("tree", [])

    for item in tree_items:
        name = item.get("path", "")
        if item.get("type") == "tree":
            name += "/"
        print(name)
