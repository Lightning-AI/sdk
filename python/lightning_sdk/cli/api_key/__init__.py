"""API key CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register API key commands with the given group."""
    from lightning_sdk.cli.api_key.create import create_api_key
    from lightning_sdk.cli.api_key.delete import delete_api_key
    from lightning_sdk.cli.api_key.get import get_api_key
    from lightning_sdk.cli.api_key.list import list_api_keys

    group.add_command(get_api_key)
    group.add_command(create_api_key)
    group.add_command(list_api_keys)
    group.add_command(delete_api_key)
