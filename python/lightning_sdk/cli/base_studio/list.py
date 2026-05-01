"""Base Studio list command."""

import click
from rich.table import Table

from lightning_sdk.base_studio import BaseStudio
from lightning_sdk.cli.utils.richt_print import rich_to_str


@click.command("list")
@click.option("--include-disabled", help="Include disabled Base Studios in the list.", is_flag=True)
def list_base_studios(include_disabled: bool) -> None:
    """List Base Studios in an org.

    Example:
        lightning base-studio list

    """
    return list_impl(include_disabled=include_disabled)


def list_impl(include_disabled: bool) -> None:
    base_studio_cls = BaseStudio()
    base_studios = base_studio_cls.list(include_disabled=include_disabled)

    table = Table(
        pad_edge=True,
    )

    table.add_column("Name")
    table.add_column("Description")
    table.add_column("Creator")
    table.add_column("Enabled")

    for base_studio in base_studios:
        table.add_row(
            base_studio.name.lower().replace(" ", "-"),
            base_studio.description or "",
            base_studio.creator,
            "Yes" if base_studio.enabled else "No",
        )

    click.echo(rich_to_str(table), color=True)
