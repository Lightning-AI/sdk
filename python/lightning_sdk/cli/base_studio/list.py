"""Base Studio list command."""

import rich_click as click
from rich.table import Table

from lightning_sdk.base_studio import BaseStudio
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.richt_print import rich_to_str


@click.command("list", cls=LightningCommand)
@click.option("--include-disabled", help="Include disabled Base Studios in the list.", is_flag=True)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_base_studios(include_disabled: bool, as_json: bool = False) -> None:
    """List Base Studios in an org.

    Example:
        lightning base-studio list

    """
    return list_impl(include_disabled=include_disabled, as_json=as_json)


def list_impl(include_disabled: bool, as_json: bool = False) -> None:
    base_studio_cls = BaseStudio()
    base_studios = base_studio_cls.list(include_disabled=include_disabled)

    if as_json:
        echo_json(
            [
                {
                    "name": base_studio.name.lower().replace(" ", "-"),
                    "description": base_studio.description or "",
                    "creator": base_studio.creator,
                    "enabled": bool(base_studio.enabled),
                }
                for base_studio in base_studios
            ]
        )
        return

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
