import shlex
import sys
import traceback
from contextlib import suppress
from time import time
from types import TracebackType
from typing import Optional, Type

import click
import rich_click
from rich.console import Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from lightning_sdk.__version__ import __version__
from lightning_sdk.cli.utils import rich_to_str
from lightning_sdk.constants import _LIGHTNING_DEBUG
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi.models.v1_create_sdk_command_history_request import (
    V1CreateSDKCommandHistoryRequest,
)
from lightning_sdk.lightning_cloud.openapi.models.v1_sdk_command_history_severity import V1SDKCommandHistorySeverity
from lightning_sdk.lightning_cloud.openapi.models.v1_sdk_command_history_type import V1SDKCommandHistoryType
from lightning_sdk.lightning_cloud.rest_client import LightningClient


def _auth_header_without_browser() -> Optional[str]:
    auth = Auth()
    if not (auth.api_key or auth.auth_token):
        try:
            if not auth.load():
                return None
        except Exception:
            return None
    try:
        return auth.auth_header
    except Exception:
        return None


def _log_command(message: str = "", duration: int = 0, error: Optional[str] = None) -> None:
    original_command = " ".join(shlex.quote(arg) for arg in sys.argv)
    auth_header = _auth_header_without_browser()
    if not auth_header:
        return

    body = V1CreateSDKCommandHistoryRequest(
        command=original_command,
        duration=duration,
        message=f"{message}",
        project_id=None,
        severity=V1SDKCommandHistorySeverity.INFO,
        type=V1SDKCommandHistoryType.CLI,
        version=__version__,
    )

    if error:
        body.severity = V1SDKCommandHistorySeverity.WARNING if error == "0" else V1SDKCommandHistorySeverity.ERROR
        body.message = body.message + f" | Error: {error}"

    # limit characters
    body.message = body.message[:1000]

    with suppress(Exception):
        client = LightningClient(retry=False, max_tries=0, with_auth=False)
        client.api_client.set_default_header("Authorization", auth_header)
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


def _gradient_rule(width: int) -> "Text":
    from rich.text import Text

    r0, g0, b0 = 0x22, 0xD3, 0xEE  # #22d3ee  cyan (design start)
    r1, g1, b1 = 0xA7, 0x8B, 0xFA  # #a78bfa  purple (design end)
    t = Text(no_wrap=True, overflow="crop")
    for i in range(width):
        frac = i / max(width - 1, 1)
        r = int(r0 + frac * (r1 - r0))
        g = int(g0 + frac * (g1 - g0))
        b = int(b0 + frac * (b1 - b0))
        t.append("─", style=f"#{r:02x}{g:02x}{b:02x}")
    return t


class CommandLoggingGroup(rich_click.RichGroup):
    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        from rich.padding import Padding
        from rich.table import Table
        from rich.text import Text

        config = formatter.config  # type: ignore[union-attr]

        if config.header_text:
            left = formatter.rich_text(config.header_text, config.style_header_text)  # type: ignore[union-attr]
            right = Text.from_markup(f"[bold #a78bfa]v{__version__}[/bold #a78bfa]")

            grid = Table.grid(expand=True)
            grid.add_column(ratio=1)
            grid.add_column(justify="right")
            grid.add_row(left, right)

            formatter.write(  # type: ignore[arg-type]
                Padding(grid, config.padding_header_text, style=config.style_padding_usage)
            )
            formatter.write("")  # type: ignore[arg-type]
            width = getattr(getattr(formatter, "console", None), "width", 80)
            formatter.write(_gradient_rule(width))  # type: ignore[arg-type]

        saved_header = config.header_text
        config.header_text = ""
        self.format_usage(ctx, formatter)
        config.header_text = saved_header

        self.format_options(ctx, formatter)
        self.format_epilog(ctx, formatter)

    def format_epilog(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        from rich.table import Table
        from rich.text import Text

        left = Text.from_markup(
            "[#8e8e9c]Get started[/#8e8e9c]  "
            "[bold #a78bfa]lightning login[/bold #a78bfa] "
            "[#5e5e6c]→[/#5e5e6c] "
            "[bold #a78bfa]lightning studio start[/bold #a78bfa]"
        )
        right = Text.from_markup(
            "[#7a7a88]DOCS[/#7a7a88]  "
            "[link=https://lightning.ai/docs][#5b8cfa]https://lightning.ai/docs[/#5b8cfa][/link]"
        )

        grid = Table.grid(expand=True)
        grid.add_column(ratio=1)
        grid.add_column(justify="right")
        grid.add_row(left, right)

        formatter.write(grid)  # type: ignore[arg-type]

    def format_usage(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        pieces = self.collect_usage_pieces(ctx)
        formatter.write_usage(f"{ctx.command_path}", " ".join(pieces) if pieces else "")

    def format_options(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        import math

        from rich.console import Group as RenderableGroup
        from rich.table import Table
        from rich_click.rich_panel import RichCommandPanel, construct_panels

        panels = construct_panels(self, ctx, formatter)  # type: ignore[arg-type]

        option_renderables = []
        command_renderables = []

        for panel in panels:
            p = panel.render(self, ctx, formatter)  # type: ignore[arg-type]
            if isinstance(p.renderable, Table) and len(p.renderable.rows) == 0:
                continue
            if isinstance(panel, RichCommandPanel):
                command_renderables.append(p)
            else:
                option_renderables.append(p)

        if not command_renderables:
            return

        mid = math.floor(len(command_renderables) / 2)
        left, right = command_renderables[:mid], command_renderables[mid:]

        if right:
            grid = Table.grid(expand=True)
            grid.add_column(ratio=1)
            grid.add_column(ratio=1)
            grid.add_row(RenderableGroup(*left), RenderableGroup(*right))
            formatter.write(grid)  # type: ignore[arg-type]
        else:
            for p in left:
                formatter.write(p)  # type: ignore[arg-type]

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
