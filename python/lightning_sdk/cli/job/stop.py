"""Job stop command."""

from typing import Optional

import rich_click as click
from rich.console import Console

from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_job, resolve_teamspace


@click.command("stop", cls=LightningCommand)
@click.argument("name")
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
def stop_job(name: str, teamspace: Optional[str] = None, as_json: bool = False) -> None:
    """Stop a job."""
    resolved_teamspace = resolve_teamspace(teamspace)
    job = resolve_job(name, resolved_teamspace)
    job.stop()
    if as_json:
        echo_json({"name": job.name, "status": "stopped"})
        return
    Console().print(f"Successfully stopped {job.name}!")
