from typing import Any

import click


class OutOfCapacityError(RuntimeError):
    """Raised when the requested machine is not available in the selected cloud account."""


class NotSupportedError(RuntimeError):
    """Raised when the requested machine is not supported in the selected cloud account."""


class DeprecatedError(RuntimeError):
    """Raised when a deprecated feature is used."""


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
