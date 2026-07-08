"""Dataset CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register dataset commands with the given group."""
    from lightning_sdk.cli.dataset.download import download_dataset

    group.add_command(download_dataset, name="download")
