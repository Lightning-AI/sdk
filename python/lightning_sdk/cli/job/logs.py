"""Job logs command."""

from contextlib import suppress
from typing import Optional

import rich_click as click

from lightning_sdk.api.logs_api import SEVERITIES
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.logs import LogSelection, read_logs, resolve_time
from lightning_sdk.cli.utils.resource_resolution import (
    resolve_job_or_mmt,
    resolve_mmt_machine,
    resolve_teamspace,
)
from lightning_sdk.mmt import MMT


@click.command("logs", cls=LightningCommand)
@click.argument("name", required=False, help="The job name. Required.")
@click.option(
    "--teamspace",
    default=None,
    help="Teamspace owner/name. Uses the configured default teamspace when omitted.",
)
@click.option("--follow", "-f", is_flag=True, default=False, help="Stream new log lines as they are produced.")
@click.option("--tail", type=int, default=None, help="Only show the last N lines.")
@click.option("--rank", type=int, default=None, help="Machine rank to read from in a multi-machine job.")
@click.option("--timestamps", is_flag=True, default=False, help="Prepend each line with its ISO-8601 timestamp.")
@click.option("--since", default=None, help='Only include lines at or after this time (e.g. "2h", RFC3339).')
@click.option("--until", default=None, help='Only include lines at or before this time (e.g. "30m", RFC3339).')
@click.option("--query", default=None, help="Only include lines containing every whitespace-separated term.")
@click.option(
    "--severity",
    type=click.Choice(SEVERITIES),
    default=None,
    help="Only include lines at or above this severity.",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output entries as a JSON array.")
def logs_job(
    name: Optional[str] = None,
    teamspace: Optional[str] = None,
    follow: bool = False,
    tail: Optional[int] = None,
    rank: Optional[int] = None,
    timestamps: bool = False,
    since: Optional[str] = None,
    until: Optional[str] = None,
    query: Optional[str] = None,
    severity: Optional[str] = None,
    as_json: bool = False,
) -> None:
    """Print the logs for a job.

    Prints a snapshot of the logs available so far. Pass --follow to stream new
    lines from a running job until it finishes or you press Ctrl-C. --query and
    --severity are applied by the server, to both the snapshot and the stream.
    Multi-machine logs are merged unless --rank selects one machine.
    """
    resolved_teamspace = resolve_teamspace(teamspace)
    resource = resolve_job_or_mmt(name, resolved_teamspace)
    selected_rank = isinstance(resource, MMT) and rank is not None
    job = resolve_mmt_machine(resource, rank) if selected_rank else resource

    if as_json:
        if rank is not None and not selected_rank:
            raise click.ClickException("--rank is not supported with --json.")
        if isinstance(job, MMT):
            labels: dict = {}
            with suppress(Exception):
                labels = {machine.resource_id: machine.name for machine in job.machines}
            selection = LogSelection(
                teamspace_id=resolved_teamspace.id,
                mmt_id=job.resource_id,
                labels=labels,
            )
        else:
            selection = LogSelection(teamspace_id=resolved_teamspace.id, job_ids=[job.resource_id])
        read_logs(
            selection,
            query=query,
            severity=severity,
            since=resolve_time(since, "--since"),
            until=resolve_time(until, "--until"),
            tail=tail,
            follow=follow,
            as_json=True,
        )
        return

    try:
        log_options = {
            "follow": follow,
            "tail": tail,
            "timestamps": timestamps,
            "since": resolve_time(since, "--since"),
            "until": resolve_time(until, "--until"),
            "query": query,
            "severity": severity,
        }
        if not isinstance(job, MMT):
            log_options["rank"] = None if selected_rank else rank
        logs = job.logs(**log_options)
        if follow:
            for line in logs:
                click.echo(line)
        elif logs:
            click.echo(logs)
    except KeyboardInterrupt:
        pass
    except RuntimeError as ex:
        raise click.ClickException(str(ex)) from ex
