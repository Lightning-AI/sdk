"""Print an access token for curl and other callers."""

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.lightning_cloud import cli_login
from lightning_sdk.lightning_cloud.login import Auth


@click.command("token", cls=LightningCommand)
def token() -> None:
    """Print an access token with at least 30 minutes left, refreshing it first when needed."""
    try:
        click.echo(cli_login.token())
        return
    except cli_login.LoginError as err:
        failure = err

    try:
        header = Auth().auth_header
    except (ValueError, ConnectionError):
        header = None
    if header and header.startswith("Bearer "):
        click.echo(header.removeprefix("Bearer "))
        return
    raise click.ClickException(str(failure)) from failure
