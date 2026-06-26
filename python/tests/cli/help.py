import os
import re
import shlex
from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner

from lightning_sdk.cli.entrypoint import main_cli

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_CLI_NAMES = {"lightning", "lightning-sdk"}


def run_cli(command: str) -> SimpleNamespace:
    args = shlex.split(command)
    if args and args[0] in _CLI_NAMES:
        args = args[1:]

    env = os.environ.copy()
    env.setdefault("COLUMNS", "80")

    runner = CliRunner()
    with patch("lightning_sdk.cli.utils.logging._log_command"):
        result = runner.invoke(
            main_cli,
            args,
            prog_name="lightning",
            env=env,
            color=False,
            catch_exceptions=False,
            terminal_width=80,
        )
    return SimpleNamespace(stdout=result.output, stderr="")


def command_text(command: str) -> str:
    result = run_cli(command)
    text = result.stdout + result.stderr
    text = _ANSI_ESCAPE_RE.sub("", text)

    for marker in ("\nError in sys.excepthook:", "\nOriginal exception was:"):
        if marker in text:
            text = text.split(marker, 1)[0]

    return text.rstrip() + "\n"


def assert_help_contains(command: str, *snippets: str) -> str:
    text = command_text(command)
    for snippet in snippets:
        assert snippet in text
    return text
