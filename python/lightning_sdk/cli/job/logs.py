"""Job logs command."""

from contextlib import suppress
from typing import Optional

import rich_click as click

from lightning_sdk.api.logs_api import SEVERITIES
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.logs import LogSelection, read_logs, resolve_time
from lightning_sdk.cli.utils.resource_resolution import resolve_job, resolve_job_machine, resolve_teamspace


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
    Multi-machine logs are merged unless --rank selects one machine, which opens
    that machine's per-job websocket (same path as a single-machine job with
    --rank).
    """
    resolved_teamspace = resolve_teamspace(teamspace)
    resource = resolve_job(name, resolved_teamspace)
    selected_rank = resource.is_multi_machine is True and rank is not None
    if selected_rank:
        assert rank is not None
        job = resolve_job_machine(resource, rank)
    else:
        job = resource

    if as_json:
        if rank is not None and not selected_rank:
            raise click.ClickException("--rank is not supported with --json.")
        if job.is_multi_machine is True:
            labels: dict = {}
            with suppress(Exception):
                labels = {
                    machine.resource_id: machine.name for machine in job.machines if machine.resource_id is not None
                }
            selection = LogSelection(
                teamspace_id=resolved_teamspace.id,
                mmt_id=job.resource_id,
                labels=labels,
            )
        else:
            if job.resource_id is None:
                raise click.ClickException("The selected job does not have a resource ID.")
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
        if job.is_multi_machine is True:
            logs = job.logs(
                follow=follow,
                tail=tail,
                timestamps=timestamps,
                since=resolve_time(since, "--since"),
                until=resolve_time(until, "--until"),
                query=query,
                severity=severity,
            )
        else:
            # Any non-None rank routes Job through the legacy per-job websocket (server-side
            # tail). For a selected MMT machine the process rank on that node is 0.
            logs = job.logs(
                follow=follow,
                tail=tail,
                rank=0 if selected_rank else rank,
                timestamps=timestamps,
                since=resolve_time(since, "--since"),
                until=resolve_time(until, "--until"),
                query=query,
                severity=severity,
            )
        if follow:
            for line in logs:
                click.echo(line)
        elif logs:
            click.echo(logs)
    except KeyboardInterrupt:
        pass
    except RuntimeError as ex:
        raise click.ClickException(str(ex)) from ex
