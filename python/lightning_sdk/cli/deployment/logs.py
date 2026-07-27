"""Deployment logs command."""

from typing import Optional, Sequence

import rich_click as click

from lightning_sdk.api.deployment_api import DeploymentApi
from lightning_sdk.api.job_api import JobApiV2
from lightning_sdk.api.logs_api import SEVERITIES, LogsApi
from lightning_sdk.cli.deployment.common import resolve_deployment, resolve_teamspace
from lightning_sdk.cli.utils.logging import LightningCommand

# A deployment whose logs are not in the current storage format yet has no saved history to
# print. Rather than show nothing, briefly tail the live stream and stop once it goes quiet.
_LIVE_FALLBACK_IDLE_TIMEOUT = 8


@click.command("logs", cls=LightningCommand)
@click.argument("name")
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace).")
@click.option("--job-id", "job_ids", multiple=True, help="Specific deployment job ID. Can be repeated.")
@click.option("--since", help="Only include logs after this timestamp.")
@click.option("--until", help="Only include logs before this timestamp.")
@click.option("--query", help="Only include lines containing every whitespace-separated term.")
@click.option(
    "--severity",
    type=click.Choice(SEVERITIES),
    help="Only include lines at or above this severity.",
)
@click.option("--rank", type=int, help="Machine of a single replica to read (legacy log path).")
@click.option("--follow", "-f", is_flag=True, default=False, help="Stream new log lines as they are produced.")
@click.option("--tail", type=int, help="Only show the last N lines of the available logs.")
@click.option("--timestamps", is_flag=True, default=False, help="Prepend each line with its ISO-8601 timestamp.")
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
) -> None:
    """Print deployment logs.

    Reads every replica by default, merged into one timeline and labelled with the replica each
    line came from. Pass --job-id (repeatable) to read specific replicas.
    """
    resolved_teamspace = resolve_teamspace(teamspace)
    api = DeploymentApi()
    deployment = resolve_deployment(api, resolved_teamspace.id, name)

    if rank is not None:
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

    jobs = api.list_deployment_jobs(resolved_teamspace.id, deployment.id, limit=100)
    if not jobs and not job_ids:
        click.echo("No jobs found for this deployment.")
        return

    names = {job.id: job.name or job.id for job in jobs}
    selected = list(job_ids)
    # Only label lines when more than one replica can show up in the stream.
    labelled = len(selected or jobs) > 1

    entries = LogsApi().stream(
        resolved_teamspace.id,
        job_ids=selected,
        # Selecting the deployment picks up replicas that start later; a job id list is fixed.
        deployment_id=None if selected else deployment.id,
        since=since,
        until=until,
        query=query,
        severity=severity,
        follow=follow,
        tail=tail,
        idle_timeout=None if follow else _LIVE_FALLBACK_IDLE_TIMEOUT,
        fallback_to_live=not follow,
    )

    try:
        for entry in entries:
            label = names.get(entry.resource_id, entry.resource_id) if labelled else None
            click.echo(entry.format(timestamps=timestamps, prefix=label))
    except KeyboardInterrupt:
        pass
    except RuntimeError as ex:
        raise click.ClickException(str(ex)) from ex


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
            since=since,
            until=until,
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
            idle_timeout=None if follow else _LIVE_FALLBACK_IDLE_TIMEOUT,
            timestamps=timestamps,
        ):
            click.echo(line)
    except KeyboardInterrupt:
        pass
    except RuntimeError as ex:
        raise click.ClickException(str(ex)) from ex
