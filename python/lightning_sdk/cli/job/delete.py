"""Job delete command."""

from typing import Optional

import rich_click as click
from rich.console import Console

from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_job_or_mmt, resolve_teamspace


@click.command("delete", cls=LightningCommand)
@click.argument("name")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "The teamspace to delete the job from. "
        "Should be specified as {owner}/{name} "
        "If not provided, uses the configured default teamspace."
    ),
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def delete_job(name: str, teamspace: Optional[str] = None, as_json: bool = False) -> None:
    """Delete a job."""
    resolved_teamspace = resolve_teamspace(teamspace)
    job = resolve_job_or_mmt(name, resolved_teamspace)
    job.delete()
    if as_json:
        echo_json({"name": job.name, "deleted": True})
        return
    Console().print(f"Successfully deleted {job.name}!")
