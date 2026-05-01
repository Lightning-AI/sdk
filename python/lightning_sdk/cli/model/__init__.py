"""Model CLI commands."""

import click


def register_commands(group: click.Group) -> None:
    """Register model commands with the given group."""
    from lightning_sdk.cli.model.download import download_model_cmd
    from lightning_sdk.cli.model.upload import upload_model

    group.add_command(upload_model, name="upload")
    group.add_command(download_model_cmd, name="download")
