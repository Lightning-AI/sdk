"""Container CLI commands."""

import click


def register_commands(group: click.Group) -> None:
    """Register container commands with the given group."""
    from lightning_sdk.cli.container.delete import delete_container
    from lightning_sdk.cli.container.download import download_container
    from lightning_sdk.cli.container.list import list_containers
    from lightning_sdk.cli.container.upload import upload_container

    group.add_command(list_containers, name="list")
    group.add_command(upload_container, name="upload")
    group.add_command(download_container, name="download")
    group.add_command(delete_container, name="delete")
