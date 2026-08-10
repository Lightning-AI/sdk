"""Pipeline CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register pipeline commands with the given group."""
    from lightning_sdk.cli.pipeline.logs import logs_pipeline

    group.add_command(logs_pipeline, name="logs")
