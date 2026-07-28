"""Container delete command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.legacy.delete import container as _delete_container
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("delete", cls=LightningCommand)
@click.argument("name")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "The teamspace to delete the container from. "
        "Should be specified as {owner}/{name}. "
        "Defaults to the configured teamspace."
    ),
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def delete_container(name: str, teamspace: Optional[str] = None, as_json: bool = False) -> None:
    """Delete the docker container NAME."""
    _delete_container.callback(name=name, teamspace=teamspace, as_json=as_json)
