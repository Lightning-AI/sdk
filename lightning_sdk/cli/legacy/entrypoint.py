import sys
import traceback
from types import TracebackType
from typing import Type

import click
from rich.console import Console, Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from lightning_sdk import __version__
from lightning_sdk.api.studio_api import _cloud_url
from lightning_sdk.cli.legacy.ai_hub import aihub
from lightning_sdk.cli.legacy.coloring import CustomHelpFormatter
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
from lightning_sdk.cli.legacy.open import open
from lightning_sdk.cli.legacy.run import run
from lightning_sdk.cli.legacy.start import start
from lightning_sdk.cli.legacy.stop import stop
from lightning_sdk.cli.legacy.switch import switch
from lightning_sdk.cli.legacy.upload import upload
from lightning_sdk.constants import _LIGHTNING_DEBUG
from lightning_sdk.lightning_cloud.login import Auth


def _notify_exception(exception_type: Type[BaseException], value: BaseException, tb: TracebackType) -> None:
    """CLI won't show tracebacks, just print the exception message."""
    console = Console()

    message = str(value.args[0]) if value.args else str(value) or "An unknown error occurred"

    error_text = Text()
    error_text.append(f"{exception_type.__name__}: ", style="bold red")
    error_text.append(message, style="white")

    renderables = [error_text]

    if _LIGHTNING_DEBUG:
        tb_text = "".join(traceback.format_exception(exception_type, value, tb))
        renderables.append(Text("\n\nFull traceback:\n", style="bold yellow"))
        renderables.append(Syntax(tb_text, "python", theme="monokai", line_numbers=False, word_wrap=True))
    else:
        renderables.append(Text("\n\n🐞 To view the full traceback, set: LIGHTNING_DEBUG=1"))

    renderables.append(Text("\n📘 Need help? Run: lightning <command> --help", style="cyan"))

    console.print(Panel(Group(*renderables), title="⚡ Lightning CLI Error", border_style="red"))


@click.group(name="lightning", help="Command line interface (CLI) to interact with/manage Lightning AI Studios.")
@click.version_option(__version__, message="Lightning CLI version %(version)s")
def main_cli() -> None:
    sys.excepthook = _notify_exception


# colorful help messages
main_cli.context_class.formatter_class = CustomHelpFormatter


@main_cli.command
def login() -> None:
    """Login to Lightning AI Studios."""
    auth = Auth()
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


# additional commands
main_cli.add_command(aihub)
main_cli.add_command(configure)
main_cli.add_command(connect)
main_cli.add_command(create)
main_cli.add_command(delete)
main_cli.add_command(dockerize)
main_cli.add_command(download)
main_cli.add_command(generate)
main_cli.add_command(inspect)
main_cli.add_command(list_cli)
main_cli.add_command(run)
main_cli.add_command(deploy)
main_cli.add_command(start)
main_cli.add_command(stop)
main_cli.add_command(switch)
main_cli.add_command(upload)
main_cli.add_command(open)


if __name__ == "__main__":
    main_cli()
