"""New Lightning CLI entrypoint with organized command groups."""

import os
import sys

import click

from lightning_sdk import __version__
from lightning_sdk.api.studio_api import _cloud_url

# Import legacy groups directly from groups.py
from lightning_sdk.cli.groups import (
    base_studio,
    config,
    # job,
    license,
    # mmt,
    studio,
    vm,
)
from lightning_sdk.cli.utils import CustomHelpFormatter
from lightning_sdk.cli.utils.logging import CommandLoggingGroup, logging_excepthook
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.utils.resolve import _get_authed_user, in_studio


@click.group(
    name="lightning",
    help="Command line interface (CLI) to interact with/manage Lightning AI Studios.",
    cls=CommandLoggingGroup,
)
@click.version_option(__version__, message="Lightning CLI version %(version)s")
def main_cli() -> None:
    sys.excepthook = logging_excepthook


main_cli.context_class.formatter_class = CustomHelpFormatter


@main_cli.command
def login() -> None:
    """Login to Lightning AI Studios."""
    # try to fetch credentials, if successful (e.g. in a Studio or already logged in), no need to relogin
    auth = Auth()
    if (auth.user_id and auth.api_key) or auth.load():
        try:
            auth_user = _get_authed_user()
            click.echo(f'You are currently logged in as "{auth_user.name}"')
        except Exception:
            click.echo("You are already logged in")
        click.echo('"lightning login" is not required within a Studio or when already logged in')
        return

    if in_studio():
        # this is unexpected, as we automatically auth within a Studio
        raise RuntimeError("Unable to login within a Studio. Did you change your shell setup?") from None

    auth.clear()
    try:
        auth.authenticate()
    except ConnectionError:
        raise RuntimeError(f"Unable to connect to {_cloud_url()}. Please check your internet connection.") from None


@main_cli.command
def logout() -> None:
    """Logout from Lightning AI Studios."""
    auth = Auth()
    auth.clear()


# Add new command groups
main_cli.add_command(config)
# main_cli.add_command(job)
# main_cli.add_command(mmt)
main_cli.add_command(studio)
main_cli.add_command(vm)
main_cli.add_command(base_studio)
main_cli.add_command(license)

if os.environ.get("LIGHTNING_EXPERIMENTAL_CLI_ONLY", "0") != "1":
    #### LEGACY COMMANDS ####
    # these commands are currently supported for backwards compatibility, but will potentially be removed in the future.
    # they've grown pretty wild and provide a very inconsistent UX.
    from lightning_sdk.cli.legacy.ai_hub import aihub
    from lightning_sdk.cli.legacy.configure import configure
    from lightning_sdk.cli.legacy.connect import connect
    from lightning_sdk.cli.legacy.create import create
    from lightning_sdk.cli.legacy.delete import delete
    from lightning_sdk.cli.legacy.deploy.serve import deploy
    from lightning_sdk.cli.legacy.docker_cli import dockerize
    from lightning_sdk.cli.legacy.download import download
    from lightning_sdk.cli.legacy.generate import generate
    from lightning_sdk.cli.legacy.inspection import inspect
    from lightning_sdk.cli.legacy.list import list_cli
    from lightning_sdk.cli.legacy.open import open as open_cmd
    from lightning_sdk.cli.legacy.run import run
    from lightning_sdk.cli.legacy.start import start
    from lightning_sdk.cli.legacy.stop import stop
    from lightning_sdk.cli.legacy.switch import switch
    from lightning_sdk.cli.legacy.upload import upload

    # Add old command groups
    main_cli.add_command(aihub)
    main_cli.add_command(configure)
    main_cli.add_command(connect)
    main_cli.add_command(create)
    main_cli.add_command(delete)
    main_cli.add_command(deploy)
    main_cli.add_command(dockerize)
    main_cli.add_command(download)
    main_cli.add_command(generate)
    main_cli.add_command(inspect)
    main_cli.add_command(list_cli)
    main_cli.add_command(open_cmd)
    main_cli.add_command(run)
    main_cli.add_command(start)
    main_cli.add_command(stop)
    main_cli.add_command(switch)
    main_cli.add_command(upload)


if __name__ == "__main__":
    main_cli()
