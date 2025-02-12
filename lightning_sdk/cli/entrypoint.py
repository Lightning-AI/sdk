import sys
from types import TracebackType
from typing import Type

import click
from fire import Fire
from lightning_utilities.core.imports import RequirementCache
from rich.console import Console
from rich.panel import Panel

from lightning_sdk.api.studio_api import _cloud_url
from lightning_sdk.cli.ai_hub import _AIHub, aihub
from lightning_sdk.cli.configure import _Configure, configure
from lightning_sdk.cli.connect import _Connect, connect
from lightning_sdk.cli.delete import _Delete, delete
from lightning_sdk.cli.download import _Downloads, download
from lightning_sdk.cli.generate import _Generate, generate
from lightning_sdk.cli.inspect import _Inspect, inspect
from lightning_sdk.cli.legacy import _LegacyLightningCLI
from lightning_sdk.cli.list import _List
from lightning_sdk.cli.run import _Run
from lightning_sdk.cli.serve import _Docker, _LitServe
from lightning_sdk.cli.start import _Start
from lightning_sdk.cli.stop import _Stop
from lightning_sdk.cli.switch import _Switch
from lightning_sdk.cli.upload import _Uploads
from lightning_sdk.lightning_cloud.login import Auth

_LIGHTNING_AVAILABLE = RequirementCache("lightning")


class StudioCLI:
    """Command line interface (CLI) to interact with/manage Lightning AI Studios."""

    def __init__(self) -> None:
        self.download = _Downloads()
        self.upload = _Uploads()
        self.aihub = _AIHub()
        self.run = _Run(legacy_run=_LegacyLightningCLI() if _LIGHTNING_AVAILABLE else None)
        self.serve = _LitServe()
        self.dockerize = _Docker()
        self.list = _List()
        self.delete = _Delete()
        self.inspect = _Inspect()
        self.stop = _Stop()
        self.start = _Start()
        self.switch = _Switch()
        self.generate = _Generate()
        self.connect = _Connect()
        self.configure = _Configure()

        sys.excepthook = _notify_exception

    def login(self) -> None:
        """Login to Lightning AI Studios."""
        return login()

    def logout(self) -> None:
        """Logout from Lightning AI Studios."""
        return logout()


def _notify_exception(exception_type: Type[BaseException], value: BaseException, tb: TracebackType) -> None:  # No
    """CLI won't show tracebacks, just print the exception message."""
    console = Console()
    console.print(Panel(value))


def main_cli() -> None:
    """CLI entrypoint."""
    Fire(StudioCLI(), name="lightning")


@click.group(name="lightning", help="Command line interface (CLI) to interact with/manage Lightning AI Studios.")
def main_cli_click() -> None:
    pass


# @main_cli_click.command
def login() -> None:
    """Login to Lightning AI Studios."""
    auth = Auth()
    auth.clear()

    try:
        auth.authenticate()
    except ConnectionError:
        raise RuntimeError(f"Unable to connect to {_cloud_url()}. Please check your internet connection.") from None


# @main_cli_click.command
def logout() -> None:
    """Logout from Lightning AI Studios."""
    auth = Auth()
    auth.clear()


# TODO: handle exception hook registration
main_cli_click.add_command(aihub)
main_cli_click.add_command(configure)
main_cli_click.add_command(connect)
main_cli_click.add_command(delete)
main_cli_click.add_command(download)
main_cli_click.add_command(generate)
main_cli_click.add_command(inspect)


if __name__ == "__main__":
    main_cli()
