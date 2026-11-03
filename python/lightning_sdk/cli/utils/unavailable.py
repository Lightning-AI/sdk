"""Temporarily unavailable CLI commands: they stay in help but refuse to run."""

from __future__ import annotations

import copy
import functools
import sys
from collections.abc import Callable, Mapping
from typing import Any, cast

import click
from rich.panel import Panel
from rich.text import Text

from lightning_sdk.cli.utils import rich_to_str
from lightning_sdk.exceptions import RECOVERY_URL, TemporarilyUnavailableError

_NAME_STYLE = "bold #a78bfa"


def render_notice(command_path: str, detail: str | None = None, *, group: bool = False, terminal: bool = False) -> str:
    """Return the styled notice for ``command_path``, as shown by both ``--help`` and a refused run.

    Args:
        command_path: The full command path, such as ``lightning studio create``.
        detail: Optional text added under the notice, such as a workaround.
        group: Whether ``command_path`` is a group whose commands are all temporarily unavailable.
        terminal: Whether the output goes to a terminal. Only then is the recovery URL a clickable link,
            since the escape codes for links are not stripped from piped output.

    Returns:
        str: The notice as a panel with ANSI styles. Strip them with :func:`click.unstyle` when not on a terminal.
    """
    if group:
        headline = Text.assemble("All commands under ", (command_path, _NAME_STYLE), " are temporarily unavailable.\n")
    else:
        headline = Text.assemble((command_path, _NAME_STYLE), " is temporarily unavailable.\n")
    body = Text.assemble(
        headline,
        "Please try again later.\n",
        ("More information: ", "dim"),
        (RECOVERY_URL, f"underline #22d3ee link {RECOVERY_URL}" if terminal else "underline #22d3ee"),
    )
    if detail:
        body.append(f"\n{detail}")
    panel = Panel(body, title="⚡ Temporarily unavailable", title_align="left", border_style="yellow", expand=False)
    return rich_to_str(panel)


def _always() -> bool:
    return True


def _always_unavailable(_params: Mapping[str, Any]) -> bool:
    return True


def _with_help_notice(
    cmd: click.Command, detail: str | None = None, *, group: bool = False, shown: Callable[[], bool] = _always
) -> click.Command:
    """Return a copy of ``cmd`` whose help starts with the notice while ``shown()``. The copy still runs as before."""
    marked = copy.copy(cmd)
    original_get_help = cmd.get_help

    def _get_help(ctx: click.Context) -> str:
        if not shown():
            return original_get_help(ctx)
        terminal = sys.stdout.isatty()
        notice = render_notice(ctx.command_path, detail, group=group, terminal=terminal)
        # The help text is printed as-is, so the styles are dropped unless it goes to a terminal.
        if not terminal:
            notice = click.unstyle(notice)
        return f"{notice}\n{original_get_help(ctx)}"

    cast(Any, marked).get_help = _get_help
    return marked


def mark_temporarily_unavailable(
    cmd: click.Command,
    detail: str | None = None,
    *,
    unavailable: Callable[[Mapping[str, Any]], bool] = _always_unavailable,
) -> click.Command:
    """Return a copy of ``cmd`` that raises :class:`TemporarilyUnavailableError` when run while it is unavailable.

    The copy keeps the original's parameters and help, and while it is unavailable its help
    text starts with the notice, so ``--help`` still works. The original is left untouched, so
    code that imports the command directly keeps working.

    ``invoke`` is replaced as well as ``callback``: a wrapper such as ``DeprecatedGroup``
    may already have wrapped ``invoke`` and would otherwise run the original command.

    Args:
        cmd: The command to mark as temporarily unavailable.
        detail: Optional text added to the notice, such as a workaround or an expected return.
        unavailable: Whether the command is unavailable, given the parameters it is run with. It is
            asked again on every run, and with no parameters for ``--help`` and the group notice.

    Returns:
        click.Command: The marked copy to register in place of ``cmd``.
    """
    marked = _with_help_notice(cmd, detail, shown=lambda: unavailable({}))
    dynamic_cmd = cast(Any, marked)
    original_callback = cmd.callback
    original_invoke = cmd.invoke

    def _refuse(ctx: click.Context) -> None:
        raise TemporarilyUnavailableError(ctx.command_path, detail)

    def _gated_callback(*args: Any, **kwargs: Any) -> Any:
        if unavailable(kwargs):
            _refuse(click.get_current_context())
        return original_callback(*args, **kwargs) if original_callback is not None else None

    def _gated_invoke(ctx: click.Context) -> Any:
        if unavailable(ctx.params):
            _refuse(ctx)
        return original_invoke(ctx)

    dynamic_cmd.callback = _gated_callback
    dynamic_cmd.invoke = _gated_invoke
    dynamic_cmd._lightning_unavailable = unavailable
    dynamic_cmd._lightning_original = cmd
    return marked


def mark_unavailable_groups(root: click.Group) -> None:
    """Add the group notice to the help of each group under ``root`` whose commands are all marked.

    The notice shows only while all of them are unavailable. Such a group still runs (it only
    shows its help), so it is not refused. Call this after the commands are marked, so that
    nested groups such as ``studio env`` count too.
    """
    for name, cmd in root.commands.items():
        if isinstance(cmd, click.Group):
            mark_unavailable_groups(cmd)
            if not _is_marked(cmd) and _all_marked(cmd):
                root.commands[name] = _with_help_notice(cmd, group=True, shown=functools.partial(_all_unavailable, cmd))


def _all_marked(cmd: click.Command) -> bool:
    """Whether ``cmd`` is marked, or is a group with at least one command and all of them are marked."""
    if _is_marked(cmd):
        return True
    if isinstance(cmd, click.Group) and cmd.commands:
        return all(_all_marked(sub) for sub in cmd.commands.values())
    return False


def _all_unavailable(cmd: click.Command) -> bool:
    """Whether ``cmd`` is unavailable, or is a group with at least one command and all of them are unavailable."""
    if is_temporarily_unavailable(cmd):
        return True
    if isinstance(cmd, click.Group) and cmd.commands:
        return all(_all_unavailable(sub) for sub in cmd.commands.values())
    return False


def _is_marked(cmd: click.Command) -> bool:
    return getattr(cmd, "_lightning_unavailable", None) is not None


def is_temporarily_unavailable(cmd: click.Command) -> bool:
    """Whether ``cmd`` was returned by :func:`mark_temporarily_unavailable` and is unavailable right now."""
    unavailable = getattr(cmd, "_lightning_unavailable", None)
    return unavailable is not None and unavailable({})


def unmarked_command(cmd: click.Command) -> click.Command:
    """Return the command :func:`mark_temporarily_unavailable` copied, or ``cmd`` if it is not marked.

    Meant for tests and tooling that exercise a command's own behaviour without the gate.
    """
    return cast(click.Command, getattr(cmd, "_lightning_original", cmd))
