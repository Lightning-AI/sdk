"""Studio open command."""

from contextlib import suppress
from pathlib import Path
from typing import Optional

import rich_click as click
from rich.console import Console

from lightning_sdk.cli.legacy.upload import _upload_folder, resolve_upload_recovery
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_teamspace
from lightning_sdk.studio import Studio
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
@click.option("--resume", is_flag=True, help="Resume an incomplete upload.")
@click.option("--restart", is_flag=True, help="Restart an incomplete upload.")
def open_studio(
    path: str = ".",
    teamspace: Optional[str] = None,
    cloud: Optional[str] = None,
    resume: bool = False,
    restart: bool = False,
) -> None:
    """Open a local file or folder in a Lightning Studio."""
    recovery = resolve_upload_recovery(resume=resume, restart=restart)
    console = Console()
    pathlib_path = Path(path).resolve()

    resolved_teamspace = resolve_teamspace(teamspace)

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
        _upload_folder(path, remote_path=".", studio=new_studio, recovery=recovery)
    else:
        new_studio.upload_file(path)

    studio_url = _get_studio_url(new_studio, turn_on=True)
    console.line()
    console.print(f"[bold]Studio URL:[/bold] {studio_url}")
