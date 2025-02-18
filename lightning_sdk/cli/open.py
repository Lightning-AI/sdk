import webbrowser
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from lightning_sdk.cli.teamspace_menu import _TeamspacesMenu
from lightning_sdk.cli.upload import _upload_folder
from lightning_sdk.studio import Studio
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.utils.resolve import _get_studio_url


@click.command("open")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option(
    "--teamspace",
    default=None,
    help=(
        "The teamspace to create the Studio in. "
        "Should be of format <OWNER>/<TEAMSPACE_NAME>. "
        "If not specified, tries to infer from the environment (e.g. when run from within a Studio.)"
    ),
)
def open(path: str = ".", teamspace: Optional[str] = None) -> None:  # noqa: A001
    """Open a local file or folder in a Lightning Studio.

    Example:
        lightning open PATH

    PATH: the path to the file or folder to open. Defaults to the current directory.
    """
    console = Console()

    pathlib_path = Path(path).resolve()

    try:
        resolved_teamspace = Teamspace()
    except ValueError:
        menu = _TeamspacesMenu()
        resolved_teamspace = menu._resolve_teamspace(teamspace=teamspace)

    new_studio = Studio(name=pathlib_path.stem, teamspace=resolved_teamspace)

    console.print(
        f"[bold]Uploading {path} to {new_studio.owner.name}/{new_studio.teamspace.name}/{new_studio.name}[/bold]"
    )

    if pathlib_path.is_dir():
        _upload_folder(path, remote_path=".", studio=new_studio)
    else:
        new_studio.upload_file(path)

    studio_url = _get_studio_url(new_studio, turn_on=True)

    console.line()
    console.print(f"[bold]Opening {new_studio.owner.name}/{new_studio.teamspace.name}/{new_studio.name}[/bold]")

    ok = webbrowser.open(studio_url)
    if not ok:
        console.print(f"Open your Studio at: {studio_url}")
