"""Temporarily unavailable CLI commands: they stay in help but refuse to run."""

from __future__ import annotations

import copy
import sys
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


def _with_help_notice(cmd: click.Command, detail: str | None = None, *, group: bool = False) -> click.Command:
    """Return a copy of ``cmd`` whose help starts with the notice. The copy still runs as before."""
    marked = copy.copy(cmd)
    original_get_help = cmd.get_help

    def _get_help(ctx: click.Context) -> str:
        terminal = sys.stdout.isatty()
        notice = render_notice(ctx.command_path, detail, group=group, terminal=terminal)
        # The help text is printed as-is, so the styles are dropped unless it goes to a terminal.
        if not terminal:
            notice = click.unstyle(notice)
        return f"{notice}\n{original_get_help(ctx)}"

    cast(Any, marked).get_help = _get_help
    return marked


def mark_temporarily_unavailable(cmd: click.Command, detail: str | None = None) -> click.Command:
    """Return a copy of ``cmd`` that raises :class:`TemporarilyUnavailableError` when run.

    The copy keeps the original's parameters and help, and its help text starts with the
    notice, so ``--help`` still works. The original is left untouched, so code that imports
    the command directly keeps working.

    ``invoke`` is replaced as well as ``callback``: a wrapper such as ``DeprecatedGroup``
    may already have wrapped ``invoke`` and would otherwise run the original command.

    Args:
        cmd: The command to mark as temporarily unavailable.
        detail: Optional text added to the notice, such as a workaround or an expected return.

    Returns:
        click.Command: The marked copy to register in place of ``cmd``.
    """
    marked = _with_help_notice(cmd, detail)
    dynamic_cmd = cast(Any, marked)

    def _refuse(ctx: click.Context) -> None:
        raise TemporarilyUnavailableError(ctx.command_path, detail)

    def _unavailable_callback(*_args: Any, **_kwargs: Any) -> None:
        _refuse(click.get_current_context())

    dynamic_cmd.callback = _unavailable_callback
    dynamic_cmd.invoke = _refuse
    dynamic_cmd._lightning_unavailable = True
    dynamic_cmd._lightning_original = cmd
    return marked


def mark_unavailable_groups(root: click.Group) -> None:
    """Add the group notice to the help of each group under ``root`` whose commands are all unavailable.

    Such a group still runs (it only shows its help), so it is not refused. Call this after the
    commands are marked, so that nested groups such as ``studio env`` count too.
    """
    for name, cmd in root.commands.items():
        if isinstance(cmd, click.Group):
            mark_unavailable_groups(cmd)
            if not is_temporarily_unavailable(cmd) and _all_unavailable(cmd):
                root.commands[name] = _with_help_notice(cmd, group=True)


def _all_unavailable(cmd: click.Command) -> bool:
    """Whether ``cmd`` is unavailable, or is a group with at least one command and all of them are unavailable."""
    if is_temporarily_unavailable(cmd):
        return True
    if isinstance(cmd, click.Group) and cmd.commands:
        return all(_all_unavailable(sub) for sub in cmd.commands.values())
    return False


def is_temporarily_unavailable(cmd: click.Command) -> bool:
    """Whether ``cmd`` was returned by :func:`mark_temporarily_unavailable`."""
    return bool(getattr(cmd, "_lightning_unavailable", False))


def unmarked_command(cmd: click.Command) -> click.Command:
    """Return the command :func:`mark_temporarily_unavailable` copied, or ``cmd`` if it is not marked.

    Meant for tests and tooling that exercise a command's own behaviour without the gate.
    """
    return cast(click.Command, getattr(cmd, "_lightning_original", cmd))
