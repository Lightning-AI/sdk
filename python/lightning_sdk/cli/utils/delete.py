"""Shared registration for resource deletion commands."""

from __future__ import annotations

from functools import partial
from typing import Any, Callable, Optional, Type

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand

DeleteAction = Callable[[], None]
DeleteResolver = Callable[[Type[Any], str, Optional[str]], DeleteAction]


def _default_delete_resolver(
    resource_cls: Type[Any],
    identifier: str,
    context: Optional[str],
    *,
    context_option: str,
    resource_kwargs: dict[str, Any],
) -> DeleteAction:
    resource = resource_cls(
        name=identifier,
        **{context_option: context},
        **resource_kwargs,
    )
    return resource.delete


def register_delete_command(
    group: click.Group,
    resource_cls: Type[Any],
    *,
    label: str,
    help: str,  # noqa: A002
    identifier: str = "name",
    context_option: str = "teamspace",
    context_help: Optional[str] = None,
    resolve_delete: Optional[DeleteResolver] = None,
    resource_kwargs: Optional[dict[str, Any]] = None,
) -> click.Command:
    """Create and directly attach a resource delete command."""
    resolver = resolve_delete or partial(
        _default_delete_resolver,
        context_option=context_option,
        resource_kwargs=dict(resource_kwargs or {}),
    )

    def callback(**params: Any) -> None:
        delete = resolver(resource_cls, params[identifier], params[context_option])
        if not params["yes"]:
            click.confirm(
                "Are you sure you want to delete?",
                default=True,
                abort=True,
            )
        delete()
        click.echo(f"{label} deleted")

    callback = click.option(
        "--yes",
        "-y",
        is_flag=True,
        default=False,
        help="Delete without prompting for confirmation.",
    )(callback)
    callback = click.option(f"--{context_option}", help=context_help)(callback)
    callback = click.argument(identifier)(callback)
    command = click.command("delete", cls=LightningCommand, help=help)(callback)
    group.add_command(command)
    return command
