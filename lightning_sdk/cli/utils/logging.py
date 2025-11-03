import shlex
import sys
import traceback
from contextlib import suppress
from time import time
from types import TracebackType
from typing import Optional, Type

import click
from rich.console import Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from lightning_sdk.__version__ import __version__
from lightning_sdk.cli.utils import rich_to_str
from lightning_sdk.constants import _LIGHTNING_DEBUG
from lightning_sdk.lightning_cloud.openapi.models.v1_create_sdk_command_history_request import (
    V1CreateSDKCommandHistoryRequest,
)
from lightning_sdk.lightning_cloud.openapi.models.v1_sdk_command_history_severity import V1SDKCommandHistorySeverity
from lightning_sdk.lightning_cloud.openapi.models.v1_sdk_command_history_type import V1SDKCommandHistoryType
from lightning_sdk.lightning_cloud.rest_client import LightningClient


def _log_command(message: str = "", duration: int = 0, error: Optional[str] = None) -> None:
    original_command = " ".join(shlex.quote(arg) for arg in sys.argv)
    client = LightningClient(retry=False, max_tries=0)

    body = V1CreateSDKCommandHistoryRequest(
        command=original_command,
        duration=duration,
        message=f"VERSION: {__version__} | {message}",
        project_id=None,
        severity=V1SDKCommandHistorySeverity.INFO,
        type=V1SDKCommandHistoryType.CLI,
    )

    if error:
        body.severity = V1SDKCommandHistorySeverity.WARNING if error == "0" else V1SDKCommandHistorySeverity.ERROR
        body.message = body.message + f" | Error: {error}"

    # limit characters
    body.message = body.message[:1000]

    with suppress(Exception):
        client.s_dk_command_history_service_create_sdk_command_history(body=body)


def _notify_exception(exception_type: Type[BaseException], value: BaseException, tb: TracebackType) -> None:
    """CLI won't show tracebacks, just print the exception message."""
    message = str(value.args[0]) if value.args else str(value) or "An unknown error occurred"

    error_text = Text()
    error_text.append(f"{exception_type.__name__}: ", style="bold red")
    error_text.append(message, style="white")

    renderables = [error_text]

    if _LIGHTNING_DEBUG:
        tb_text = "".join(traceback.format_exception(exception_type, value, tb))
        renderables.append(Text("\n\nFull traceback:\n", style="bold yellow"))
        renderables.append(Syntax(tb_text, "python", theme="monokai light", line_numbers=False, word_wrap=True))
    else:
        renderables.append(Text("\n\n🐞 To view the full traceback, set: LIGHTNING_DEBUG=1"))

    renderables.append(Text("\n📘 Need help? Run: lightning <command> --help", style="cyan"))

    text = rich_to_str(Panel(Group(*renderables), title="⚡ Lightning CLI Error", border_style="red"))
    click.echo(text, color=True)


def logging_excepthook(exception_type: Type[BaseException], value: BaseException, tb: TracebackType) -> None:
    try:
        tb_str = "".join(traceback.format_exception(exception_type, value, tb))
        ctx = click.get_current_context(silent=True)
        command_context = ctx.command_path if ctx else "outside_command_context"

        message = (
            f"Command: {command_context} | Type: {exception_type.__name__!s} | Value: {value!s} | Traceback: {tb_str}"
        )
        _log_command(message=message)
    finally:
        _notify_exception(exception_type, value, tb)


class CommandLoggingGroup(click.Group):
    def _format_ctx(self, ctx: click.Context) -> str:
        parts = []
        for k, v in ctx.params.items():
            if v is True:
                parts.append(f"--{k}")
            elif v is False or v is None:
                continue
            else:
                parts.append(f"--{k} {v}")
        params = " ".join(parts)
        args = " ".join(ctx.args)
        return (
            f"""Commands: {ctx.command_path} | Subcommand: {ctx.invoked_subcommand} | Params: {params} | Args:{args}"""
        )

    def invoke(self, ctx: click.Context) -> any:
        """Overrides the default invoke to wrap command execution with tracking."""
        start_time = time()
        error_message = None

        try:
            return super().invoke(ctx)
        except click.ClickException as e:
            error_message = str(e)
            e.show()
            ctx.exit(e.exit_code)
        except Exception as e:
            error_message = str(e)
            raise
        finally:
            _log_command(
                message=self._format_ctx(ctx),
                duration=int(time() - start_time),
                error=error_message,
            )
