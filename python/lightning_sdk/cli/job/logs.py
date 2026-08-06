"""Job logs command."""

from contextlib import suppress
from typing import Dict, Optional

import rich_click as click

from lightning_sdk.api.logs_api import SEVERITIES
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.logs import print_log_entries, resolve_time
from lightning_sdk.cli.utils.resource_resolution import resolve_job, resolve_teamspace


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
    Multi-machine logs are merged unless --rank selects one machine (same LogsApi
    path as reading that machine by name).
    """
    resolved_teamspace = resolve_teamspace(teamspace)
    job = resolve_job(name, resolved_teamspace)

    labels: Optional[Dict[str, str]] = None
    if job.is_multi_machine is True and rank is None:
        labels = {}
        with suppress(Exception):
            labels = {machine.resource_id: machine.name for machine in job.machines}

    try:
        entries = job.iter_log_entries(
            follow=follow,
            tail=tail,
            rank=rank,
            since=resolve_time(since, "--since"),
            until=resolve_time(until, "--until"),
            query=query,
            severity=severity,
        )
        print_log_entries(
            entries,
            query=query,
            timestamps=timestamps,
            as_json=as_json,
            follow=follow,
            labels=labels,
        )
    except KeyboardInterrupt:
        pass
    except (RuntimeError, ValueError) as ex:
        raise click.ClickException(str(ex)) from ex
