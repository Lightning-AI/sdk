"""Auth CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register auth commands with the given group."""
    from lightning_sdk.cli.auth.role import role
    from lightning_sdk.cli.auth.roles import roles
    from lightning_sdk.cli.auth.whoami import whoami

    group.add_command(whoami)
    group.add_command(roles)
    group.add_command(role)
