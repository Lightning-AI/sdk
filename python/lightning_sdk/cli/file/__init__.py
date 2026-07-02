"""File CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register file commands with the given group."""
    from lightning_sdk.cli.file.download import download_file
    from lightning_sdk.cli.file.upload import upload_file

    group.add_command(upload_file, name="upload")
    group.add_command(download_file, name="download")
