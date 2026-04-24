"""Machine list command."""

import click
from rich.console import Console
from rich.table import Table

from lightning_sdk import Machine


@click.command("list")
def list_machines() -> None:
    """Display the list of available machines."""
    table = Table(pad_edge=True)
    table.add_column("Name")

    machine_types = [
        name
        for name in dir(Machine)
        if isinstance(getattr(Machine, name), Machine) and getattr(Machine, name)._include_in_cli
    ]

    for name in sorted(machine_types):
        table.add_row(name)

    Console().print(table)
