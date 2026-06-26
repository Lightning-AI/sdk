"""Folder upload command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.legacy.upload import folder as _upload_folder
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("upload", cls=LightningCommand)
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--studio",
    default=None,
    help=(
        "The name of the studio to upload to. "
        "Will show a menu for selection if not specified. "
        "If provided, should be in the form of <TEAMSPACE-NAME>/<STUDIO-NAME>"
    ),
)
@click.option(
    "--remote-path",
    "--remote_path",
    default=None,
    help=(
        "The path where the uploaded file should appear on your Studio. "
        "Has to be within your Studio's home directory and will be relative to that. "
        "If not specified, will use the name of the folder you want to upload and place it in your home directory."
    ),
)
def upload_folder(path: str, studio: Optional[str], remote_path: Optional[str]) -> None:
    """Upload a folder to a Studio."""
    _upload_folder.callback(path=path, studio=studio, remote_path=remote_path)
