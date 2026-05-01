"""File download command."""

from typing import Optional

import click

from lightning_sdk.cli.legacy.download import file as _download_file


@click.command("download")
@click.argument("path")
@click.option(
    "--studio",
    default=None,
    help=(
        "The name of the studio to download from. "
        "Will show a menu with user's owned studios for selection if not specified. "
        "If provided, should be in the form of <TEAMSPACE-NAME>/<STUDIO-NAME> where the names are case-sensitive. "
        "The teamspace and studio names can be regular expressions to match, "
        "a menu filtered studios will be shown for final selection."
    ),
)
@click.option(
    "--teamspace", default=None, help="The teamspace the file is part of. Should be of format <OWNER>/<TEAMSPACE_NAME>."
)
@click.option(
    "--local-path",
    "--local_path",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="The path to the directory you want to download the file to.",
)
def download_file(
    path: str = "", studio: Optional[str] = None, teamspace: Optional[str] = None, local_path: str = "."
) -> None:
    """Download a file from a Studio or Teamspace drive file."""
    _download_file.callback(path=path, studio=studio, teamspace=teamspace, local_path=local_path)
