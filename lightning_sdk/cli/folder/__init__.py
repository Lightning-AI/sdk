"""Folder CLI commands."""

import click


def register_commands(group: click.Group) -> None:
    """Register folder commands with the given group."""
    from lightning_sdk.cli.folder.download import download_folder
    from lightning_sdk.cli.folder.upload import upload_folder

    group.add_command(upload_folder, name="upload")
    group.add_command(download_folder, name="download")
