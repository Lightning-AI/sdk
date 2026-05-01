"""Container delete command."""

from typing import Optional

import click

from lightning_sdk.cli.legacy.delete import container as _delete_container


@click.command("delete")
@click.argument("name")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "The teamspace to delete the container from. "
        "Should be specified as {owner}/{name} "
        "If not provided, can be selected in an interactive menu."
    ),
)
def delete_container(name: str, teamspace: Optional[str] = None) -> None:
    """Delete the docker container NAME."""
    _delete_container.callback(name=name, teamspace=teamspace)
