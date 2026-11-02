import sys
from typing import IO, Any, Optional

import click

RECOVERY_URL = "https://platform.lightning.ai/recovery"


class OutOfCapacityError(RuntimeError):
    """Raised when the requested machine is not available in the selected cloud account."""


class NotSupportedError(RuntimeError):
    """Raised when the requested machine is not supported in the selected cloud account."""


class DeprecatedError(RuntimeError):
    """Raised when a deprecated feature is used."""


class TemporarilyUnavailableError(click.ClickException):
    """Raised when a CLI command is temporarily unavailable and cannot be run right now.

    ``str()`` gives the plain notice, which the logs record. ``show`` prints the styled notice instead of
    the usual error line, so it matches what ``--help`` shows.
    """

    def __init__(self, command_path: str, detail: Optional[str] = None) -> None:
        message = f"{command_path} is temporarily unavailable. Please try again later. More information: {RECOVERY_URL}"
        super().__init__(f"{message} {detail}" if detail else message)
        self.command_path = command_path
        self.detail = detail

    def show(self, file: Optional[IO[Any]] = None) -> None:
        """Print the styled notice to ``file``, or stderr."""
        from lightning_sdk.cli.utils.unavailable import render_notice  # lazy: that module imports this one

        stream = file if file is not None else sys.stderr
        click.echo(render_notice(self.command_path, self.detail, terminal=stream.isatty()), file=stream, nl=False)


class DeprecatedCommand(click.Command):
    """Custom exception for deprecated commands."""

    def __init__(self, *args: Any, message: str, **kwargs: Any) -> None:
        """Create a deprecated CLI command that raises on use.

        Args:
            *args: Positional arguments forwarded to ``click.Command``.
            message: The deprecation message shown when the command is invoked or help is requested.
            **kwargs: Keyword arguments forwarded to ``click.Command``.
        """
        super().__init__(*args, **kwargs)
        self.deprecated_message = message

    def get_help(self, ctx: click.Context) -> str:
        """Raise ``DeprecatedError`` instead of showing help for deprecated commands.

        Args:
            ctx: The Click context for the current invocation.

        Returns:
            str: The help text (only reached if no deprecation message is set).

        Raises:
            DeprecatedError: Always raised when ``deprecated_message`` is set.
        """
        if self.deprecated_message:
            raise DeprecatedError(self.deprecated_message)
        return super().get_help(ctx)

    def invoke(self, ctx: click.Context) -> Any:
        """Raise ``DeprecatedError`` instead of running the deprecated command.

        Args:
            ctx: The Click context for the current invocation.

        Returns:
            Any: The return value of the parent invocation (only reached if no deprecation message is set).

        Raises:
            DeprecatedError: Always raised when ``deprecated_message`` is set.
        """
        if self.deprecated_message:
            raise DeprecatedError(self.deprecated_message)
        return super().invoke(ctx)
