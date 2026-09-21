"""Job tag command."""

from typing import Optional

import rich_click as click
from rich.console import Console

from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_job, resolve_teamspace


@click.command("tag", cls=LightningCommand)
@click.argument("name")
@click.argument("tags", nargs=-1, required=True)
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
def tag_job(name: str, tags: tuple[str, ...], teamspace: Optional[str] = None, as_json: bool = False) -> None:
    """Add tags to a job.

    Adding a tag that already exists on the job is a no-op for that tag.

        lightning job tag my-job prod gpu
    """
    resolved_teamspace = resolve_teamspace(teamspace)
    job = resolve_job(name, resolved_teamspace)
    job.set_tags(list({*job.tags, *tags}))
    current_tags = list(job.tags)
    if as_json:
        echo_json({"name": job.name, "tags": current_tags})
        return
    Console().print(f"Tags set on '{job.name}': {', '.join(current_tags)}")
