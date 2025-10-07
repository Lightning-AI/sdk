"""Base Studio list command."""

import click
from rich.table import Table

from lightning_sdk.base_studio import BaseStudio
from lightning_sdk.cli.utils.richt_print import rich_to_str


@click.command("list")
def list_base_studios() -> None:
    """List Base Studios in an org.

    Example:
        lightning base-studio list

    """
    return list_impl()


def list_impl() -> None:
    base_studio_cls = BaseStudio()
    base_studios = base_studio_cls.list() + base_studio_cls.list(managed=False)

    table = Table(
        pad_edge=True,
    )

    table.add_column("Name")
    table.add_column("Description")

    for base_studio in base_studios:
        table.add_row(
            base_studio.name.lower().replace(" ", "-"),
            base_studio.description or "",
        )

    click.echo(rich_to_str(table), color=True)
