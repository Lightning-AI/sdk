"""Dataset CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register dataset commands with the given group."""
    from lightning_sdk.cli.dataset.download import download_dataset
    from lightning_sdk.cli.dataset.upload import upload_dataset_cmd

    group.add_command(download_dataset, name="download")
    group.add_command(upload_dataset_cmd, name="upload")
