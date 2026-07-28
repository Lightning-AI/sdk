"""Job logs command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_job, resolve_teamspace


@click.command("logs", cls=LightningCommand)
@click.argument("name", required=False, help="The job name. Required.")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the name of the teamspace the job lives in. "
        "Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace). "
        "If not specified can be selected interactively."
    ),
)
@click.option("--follow", "-f", is_flag=True, default=False, help="Stream new log lines as they are produced.")
@click.option("--tail", type=int, default=None, help="Only show the last N lines.")
@click.option("--rank", type=int, default=None, help="Distributed job rank to read from (running jobs only).")
@click.option("--timestamps", is_flag=True, default=False, help="Prepend each line with its ISO-8601 timestamp.")
def logs_job(
    name: Optional[str] = None,
    teamspace: Optional[str] = None,
    follow: bool = False,
    tail: Optional[int] = None,
    rank: Optional[int] = None,
    timestamps: bool = False,
) -> None:
    """Print the logs for a job.

    Prints a snapshot of the logs available so far. Pass --follow to stream new
    lines from a running job until it finishes or you press Ctrl-C.
    """
    resolved_teamspace = resolve_teamspace(teamspace)
    job = resolve_job(name, resolved_teamspace)

    try:
        logs = job.logs(follow=follow, tail=tail, rank=rank, timestamps=timestamps)
        if follow:
            for line in logs:
                click.echo(line)
        elif logs:
            click.echo(logs)
    except KeyboardInterrupt:
        pass
    except RuntimeError as ex:
        raise click.ClickException(str(ex)) from ex
