"""Base Studio CLI commands."""

import click


def register_commands(group: click.Group) -> None:
    """Register base studio commands with the given group."""
    from lightning_sdk.cli.license.get import get_license
    from lightning_sdk.cli.license.list import list_licenses
    from lightning_sdk.cli.license.set import set_license

    group.add_command(list_licenses)
    group.add_command(get_license)
    group.add_command(set_license)
