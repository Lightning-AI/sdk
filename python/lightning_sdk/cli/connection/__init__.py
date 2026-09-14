"""Data connection CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register data connection commands with the given group."""
    from lightning_sdk.cli.connection.credentials import connection_credentials

    group.add_command(connection_credentials, name="credentials")
