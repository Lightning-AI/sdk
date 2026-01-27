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
        super().__init__(*args, **kwargs)
        self.deprecated_message = message

    def get_help(self, ctx: click.Context) -> str:
        if self.deprecated_message:
            raise DeprecatedError(self.deprecated_message)
        return super().get_help(ctx)

    def invoke(self, ctx: click.Context) -> Any:
        if self.deprecated_message:
            raise DeprecatedError(self.deprecated_message)
        return super().invoke(ctx)
