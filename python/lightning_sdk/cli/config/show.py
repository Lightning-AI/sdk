import click

from lightning_sdk.utils.config import Config


@click.command("show")
def show() -> None:
    """Show configuration values."""
    click.echo(Config())
