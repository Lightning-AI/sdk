import webbrowser
from contextlib import suppress
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from lightning_sdk.cli.legacy.upload import _upload_folder
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
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
@click.option(
    "--cloud-account",
    "--cloud_account",
    default=None,
    help=(
        "The cloud account to create the studio on. "
        "If not specified, will try to infer from the environment (e.g. when run from within a Studio.) "
        "or fall back to the teamspace default."
    ),
)
def open(path: str = ".", teamspace: Optional[str] = None, cloud_account: Optional[str] = None) -> None:  # noqa: A001
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
        menu = TeamspacesMenu()
        resolved_teamspace = menu(teamspace=teamspace)

    # default cloud account to current studios cloud account if run from studio
    # else it will fall back to teamspace default in the backend
    if cloud_account is None:
        with suppress(ValueError):
            s = Studio()
            if s.teamspace.name == resolved_teamspace.name and s.teamspace.owner.name == resolved_teamspace.owner.name:
                cloud_account = s.cloud_account

    new_studio = Studio(name=pathlib_path.stem, teamspace=resolved_teamspace, cloud_account=cloud_account)

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
