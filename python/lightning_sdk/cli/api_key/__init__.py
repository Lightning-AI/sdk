"""API key CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register API key commands with the given group."""
    from lightning_sdk.cli.api_key.common import ORG_OPTION_HELP
    from lightning_sdk.cli.api_key.create import create_api_key
    from lightning_sdk.cli.api_key.delete import ApiKeyApi, resolve_api_key_delete
    from lightning_sdk.cli.api_key.get import get_api_key
    from lightning_sdk.cli.api_key.list import list_api_keys
    from lightning_sdk.cli.utils.delete import register_delete_command

    group.add_command(get_api_key)
    group.add_command(create_api_key)
    group.add_command(list_api_keys)
    register_delete_command(
        group,
        ApiKeyApi,
        label="API key",
        help="Delete an org-scoped API key.",
        identifier="key_id",
        context_option="org",
        context_help=ORG_OPTION_HELP,
        resolve_delete=resolve_api_key_delete,
    )
