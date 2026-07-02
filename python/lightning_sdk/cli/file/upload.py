"""File upload command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.legacy.upload import file as _upload_file
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
        "If not specified, will use the name of the file you want to upload and place it in your home directory."
    ),
)
def upload_file(path: str, studio: Optional[str] = None, remote_path: Optional[str] = None) -> None:
    """Upload a file to a Studio."""
    _upload_file.callback(path=path, studio=studio, remote_path=remote_path)
