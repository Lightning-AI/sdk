"""Print the credential requests send, for curl and other callers."""

import os

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.lightning_cloud import cli_login, env
from lightning_sdk.lightning_cloud.credentials import Credential, CredentialKind, CredentialSource

_NOT_LOGGED_IN = "You are not logged in. Run `lightning login`."


def _note(credential: Credential) -> str:
    if credential.kind is CredentialKind.TOKEN_FILE:
        path = os.environ.get(env.LIGHTNING_AUTH_TOKEN_FILE, "")
        origin = f"the token file {path}"
    elif credential.kind is CredentialKind.ENV_TOKEN:
        origin = "LIGHTNING_AUTH_TOKEN"
    elif credential.kind is CredentialKind.SERVICE_ACCOUNT:
        return (
            "This token was exchanged for the service-account key in LIGHTNING_API_KEY "
            "and lasts an hour. It is what requests send."
        )
    else:
        origin = "the interim session login"
    return f"This token is from {origin}. It is what requests send."


@click.command("token", cls=LightningCommand)
def token() -> None:
    """Print the credential requests send. A saved login has at least 30 minutes left."""
    try:
        credential = CredentialSource().resolve()
    except (OSError, cli_login.LoginError) as err:
        raise click.ClickException(str(err)) from err
    if credential is None:
        raise click.ClickException(_NOT_LOGGED_IN)
    if credential.kind is CredentialKind.LOGIN:
        try:
            click.echo(cli_login.token())
        except cli_login.LoginError as err:
            raise click.ClickException(str(err)) from err
        return
    click.echo(_note(credential), err=True)
    click.echo(credential.token)
