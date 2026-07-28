"""Machine list command."""

import rich_click as click
from rich.console import Console
from rich.table import Table

from lightning_sdk import Machine
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("list", cls=LightningCommand)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_machines(as_json: bool = False) -> None:
    """Display the list of available machines."""
    machine_types = sorted(
        name
        for name in dir(Machine)
        if isinstance(getattr(Machine, name), Machine) and getattr(Machine, name)._include_in_cli
    )

    if as_json:
        echo_json([{"name": name} for name in machine_types])
        return

    table = Table(pad_edge=True)
    table.add_column("Name")
    for name in machine_types:
        table.add_row(name)

    Console().print(table)
