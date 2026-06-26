import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.utils.config import Config


@click.command("show", cls=LightningCommand)
def show() -> None:
    """Show configuration values."""
    click.echo(Config())
