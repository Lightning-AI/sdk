"""Job rename command."""

from typing import Optional

import rich_click as click
from rich.console import Console

from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_job, resolve_teamspace


@click.command("rename", cls=LightningCommand)
@click.argument("name")
@click.argument("new_name")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the name of the teamspace the job lives in. "
        "Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace). "
        "If not specified, uses the configured default teamspace."
    ),
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def rename_job(name: str, new_name: str, teamspace: Optional[str] = None, as_json: bool = False) -> None:
    """Rename a job."""
    resolved_teamspace = resolve_teamspace(teamspace)
    job = resolve_job(name, resolved_teamspace)
    job.rename(new_name)
    if as_json:
        echo_json({"name": job.name, "status": "renamed"})
        return
    Console().print(f"Successfully renamed job to '{job.name}'!")
