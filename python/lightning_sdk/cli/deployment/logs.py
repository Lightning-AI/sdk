"""Deployment logs command.

Reads every replica of a deployment, merged into one timeline. The reading and rendering live
in :mod:`lightning_sdk.cli.utils.logs`, shared with the other per-resource log commands.
"""

from typing import Optional, Sequence

import rich_click as click

from lightning_sdk.api.deployment_api import DeploymentApi
from lightning_sdk.api.job_api import JobApiV2
from lightning_sdk.api.logs_api import SEVERITIES
from lightning_sdk.cli.deployment.common import resolve_deployment, resolve_teamspace
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.logs import (
    LIVE_FALLBACK_IDLE_TIMEOUT,
    LogSelection,
    deployment_replica_labels,
    read_logs,
    resolve_time,
)

_DEFAULT_TAIL = 100


@click.command("logs", cls=LightningCommand)
@click.argument("name")
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace).")
@click.option("--job-id", "job_ids", multiple=True, help="Specific deployment job ID. Can be repeated.")
@click.option("--since", help='Only include lines at or after this time (e.g. "2h", RFC3339).')
@click.option("--until", help='Only include lines at or before this time (e.g. "30m", RFC3339).')
@click.option("--query", help="Only include lines containing every whitespace-separated term.")
@click.option(
    "--severity",
    type=click.Choice(SEVERITIES),
    help="Only include lines at or above this severity.",
)
@click.option("--rank", type=int, help="Machine of a single replica to read (legacy log path).")
@click.option("--follow", "-f", is_flag=True, default=False, help="Stream new log lines as they are produced.")
@click.option("--tail", type=int, help=f"Only show the last N lines. Defaults to {_DEFAULT_TAIL}.")
@click.option("--timestamps", is_flag=True, default=False, help="Prepend each line with its ISO-8601 timestamp.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output entries as a JSON array.")
def deployment_logs(
    name: str,
    teamspace: Optional[str] = None,
    job_ids: Sequence[str] = (),
    since: Optional[str] = None,
    until: Optional[str] = None,
    query: Optional[str] = None,
    severity: Optional[str] = None,
    rank: Optional[int] = None,
    follow: bool = False,
    tail: Optional[int] = None,
    timestamps: bool = False,
    as_json: bool = False,
) -> None:
    """Print deployment logs.

    Reads every replica by default, merged into one timeline and labelled with the replica each
    line came from. Pass --job-id (repeatable) to read specific replicas.
    """
    resolved_teamspace = resolve_teamspace(teamspace)
    api = DeploymentApi()
    deployment = resolve_deployment(api, resolved_teamspace.id, name)

    if rank is not None:
        if as_json:
            raise click.ClickException("--json is not supported with --rank (the legacy single-replica path).")
        _ranked_logs(
            api,
            resolved_teamspace.id,
            deployment.id,
            job_ids,
            since=since,
            until=until,
            rank=rank,
            follow=follow,
            tail=tail,
            timestamps=timestamps,
        )
        return

    selected = list(job_ids)
    if not selected:
        jobs = api.list_deployment_jobs(resolved_teamspace.id, deployment.id, limit=100)
        if not jobs:
            click.echo("No jobs found for this deployment.")
            return
        labels = {job.id: job.name or job.id for job in jobs} if len(jobs) > 1 else {}
    else:
        labels = deployment_replica_labels(resolved_teamspace.id, deployment.id) if len(selected) > 1 else {}

    read_logs(
        LogSelection(
            teamspace_id=resolved_teamspace.id,
            job_ids=selected,
            # Selecting the deployment picks up replicas that start later; a job id list is fixed.
            deployment_id=None if selected else deployment.id,
            labels=labels,
        ),
        query=query,
        severity=severity,
        since=resolve_time(since, "--since"),
        until=resolve_time(until, "--until"),
        # A deployment's history can span months of replicas. With no tail and no range asked
        # for, show the recent tail rather than paging from the beginning of time.
        tail=_DEFAULT_TAIL if tail is None and since is None and until is None else tail,
        follow=follow,
        timestamps=timestamps,
        as_json=as_json,
    )


def _ranked_logs(
    api: DeploymentApi,
    teamspace_id: str,
    deployment_id: str,
    job_ids: Sequence[str],
    *,
    since: Optional[str],
    until: Optional[str],
    rank: int,
    follow: bool,
    tail: Optional[int],
    timestamps: bool,
) -> None:
    """Read one machine of one replica over the legacy per-job log path.

    --rank selects a machine inside a replica, which the merged logs API has no equivalent for:
    it returns every machine's lines tagged with the replica instead. Until it does, a ranked
    read uses the older per-job endpoints, and those serve a single replica at a time.
    """
    if len(job_ids) > 1:
        raise click.ClickException("--rank reads one replica at a time; pass a single --job-id.")

    if job_ids:
        job_id = job_ids[0]
    else:
        jobs = api.list_deployment_jobs(teamspace_id, deployment_id, limit=100)
        if not jobs:
            click.echo("No jobs found for this deployment.")
            return
        if len(jobs) > 1:
            raise click.ClickException("This deployment has several replicas; pass --job-id to pick one for --rank.")
        job_id = jobs[0].id

    entries = list(
        api.iter_job_log_entries(
            teamspace_id,
            job_id,
            deployment_id=deployment_id,
            since=resolve_time(since, "--since"),
            until=resolve_time(until, "--until"),
            rank=rank,
        )
    )
    if tail is not None:
        entries = entries[-tail:]
    for entry in entries:
        click.echo(entry.format(timestamps=timestamps))

    if not follow and entries:
        return

    try:
        for line in JobApiV2().stream_logs(
            job_id=job_id,
            teamspace_id=teamspace_id,
            follow=follow,
            tail=tail,
            rank=rank,
            idle_timeout=None if follow else LIVE_FALLBACK_IDLE_TIMEOUT,
            timestamps=timestamps,
        ):
            click.echo(line)
    except KeyboardInterrupt:
        pass
    except RuntimeError as ex:
        raise click.ClickException(str(ex)) from ex
