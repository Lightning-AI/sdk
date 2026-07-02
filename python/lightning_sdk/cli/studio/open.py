"""Studio open command."""

import webbrowser
from contextlib import suppress
from pathlib import Path
from typing import Optional

import rich_click as click
from rich.console import Console

from lightning_sdk.cli.legacy.upload import _upload_folder
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.studio import Studio
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.utils.resolve import _get_studio_url


@click.command("open", cls=LightningCommand)
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option(
    "--teamspace",
    default=None,
    help=(
        "The teamspace to create the Studio in. Should be of format <OWNER>/<TEAMSPACE_NAME>. "
        "If not specified, tries to infer from the environment (e.g. when run from within a Studio.)"
    ),
)
@click.option(
    "--cloud",
    default=None,
    help="Cloud provider or cloud account to create the studio on.",
)
def open_studio(path: str = ".", teamspace: Optional[str] = None, cloud: Optional[str] = None) -> None:
    """Open a local file or folder in a Lightning Studio."""
    console = Console()
    pathlib_path = Path(path).resolve()

    try:
        resolved_teamspace = Teamspace()
    except ValueError:
        menu = TeamspacesMenu()
        resolved_teamspace = menu(teamspace=teamspace)

    if cloud is None:
        with suppress(ValueError):
            studio = Studio()
            if (
                studio.teamspace.name == resolved_teamspace.name
                and studio.teamspace.owner.name == resolved_teamspace.owner.name
            ):
                cloud = studio.cloud_account

    new_studio = Studio(name=pathlib_path.stem, teamspace=resolved_teamspace, cloud=cloud)
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
        console.print(studio_url)
