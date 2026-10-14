"""Deployment logs command.

Reads every replica of a deployment, merged into one timeline. The reading and rendering live
in :mod:`lightning_sdk.cli.utils.logs`, shared with the other per-resource log commands.
"""

import shlex
from typing import Optional, Sequence

import rich_click as click

from lightning_sdk.api.deployment_api import DeploymentApi
from lightning_sdk.api.job_api import JobApiV2
from lightning_sdk.api.logs_api import SEVERITIES
from lightning_sdk.api.mmt_api import MMTApiV2
from lightning_sdk.cli.deployment.common import resolve_deployment, resolve_teamspace
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.logs import (
    LogSelection,
    deployment_replica_labels,
    make_logs_group,
    read_logs,
    resolve_time,
    run_download,
)

_DEFAULT_TAIL = 100


def _command_without_tui(
    name: str,
    *,
    teamspace: Optional[str],
    job_ids: Sequence[str],
    since: Optional[str],
    until: Optional[str],
    query: Optional[str],
    severity: Optional[str],
    rank: Optional[int],
    tail: Optional[int],
    follow: bool,
    timestamps: bool,
    as_json: bool,
) -> str:
    """Reconstruct the invoked ``deployment logs`` command with ``--interactive`` dropped.

    Only the options actually passed are re-emitted, each shell-quoted, so the string is safe to
    copy-paste back verbatim.
    """
    parts = ["lightning", "deployment", "logs", name]
    if teamspace:
        parts += ["--teamspace", teamspace]
    for job_id in job_ids:
        parts += ["--job-id", job_id]
    if since:
        parts += ["--since", since]
    if until:
        parts += ["--until", until]
    if query:
        parts += ["--query", query]
    if severity:
        parts += ["--severity", severity]
    if rank is not None:
        parts += ["--rank", str(rank)]
    if tail is not None:
        parts += ["--tail", str(tail)]
    if follow:
        parts.append("--follow")
    if timestamps:
        parts.append("--timestamps")
    if as_json:
        parts.append("--json")
    return " ".join(shlex.quote(part) for part in parts)


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
@click.option("--rank", type=int, help="Machine (0-based) to read within a multi-machine replica.")
@click.option("--follow", "-f", is_flag=True, default=False, help="Stream new log lines as they are produced.")
@click.option("--tail", type=int, help=f"Only show the last N lines. Defaults to {_DEFAULT_TAIL}.")
@click.option("--timestamps", is_flag=True, default=False, help="Prepend each line with its ISO-8601 timestamp.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output entries as a JSON array.")
@click.option("--interactive", "-i", "tui", is_flag=True, default=False, help="Launch the interactive TUI log viewer.")
def _deployment_logs_cmd(
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
    tui: bool = False,
) -> None:
    """Print deployment logs.

    Reads every replica by default, merged into one timeline and labelled with the replica each
    line came from. Pass --job-id (repeatable) to read specific replicas.
    """
    resolved_teamspace = resolve_teamspace(teamspace)
    api = DeploymentApi()
    deployment = resolve_deployment(api, resolved_teamspace.id, name)

    if tui:
        from lightning_sdk.cli.logs_tui import run_tui

        # TUI reads merged stream, incompatible with --rank
        if rank is not None:
            without_tui = _command_without_tui(
                name,
                teamspace=teamspace,
                job_ids=job_ids,
                since=since,
                until=until,
                query=query,
                severity=severity,
                rank=rank,
                tail=tail,
                follow=follow,
                timestamps=timestamps,
                as_json=as_json,
            )
            raise click.ClickException(f"TUI view does not support --rank. Instead, use:\n    {without_tui}")

        selected = list(job_ids)
        jobs = api.list_deployment_jobs(resolved_teamspace.id, deployment.id, limit=100)
        replicas = [job for job in jobs if job.id in selected] if selected else jobs
        labels = {job.id: job.name or job.id for job in replicas} if len(replicas) > 1 else {}

        run_tui(
            LogSelection(
                teamspace_id=resolved_teamspace.id,
                job_ids=selected,
                deployment_id=None if selected else deployment.id,
                labels=labels,
            ),
            follow=(follow or (since is None and until is None)),
            tail=tail,
            show_timestamps=True,
            since=since,
            until=until,
            query=query,
            title=f"{resolved_teamspace.owner.name}/{resolved_teamspace.name}/{deployment.name} logs",
        )
        return

    if rank is not None:
        if as_json:
            raise click.ClickException("--json is not supported with --rank (a single machine's stream).")
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
    """Read one machine of one replica through the logs API.

    ``--rank`` selects a machine inside a replica. The logs API has no rank parameter and
    serves each machine as its own job, so the machine's job id is resolved client-side and
    read like any other job.
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

    read_logs(
        LogSelection(teamspace_id=teamspace_id, job_ids=[_resolve_ranked_job_id(teamspace_id, job_id, rank)]),
        since=resolve_time(since, "--since"),
        until=resolve_time(until, "--until"),
        tail=tail,
        follow=follow,
        timestamps=timestamps,
    )


def _resolve_ranked_job_id(teamspace_id: str, job_id: str, rank: int) -> str:
    """The job id of machine ``rank`` (0-based) within ``job_id``'s multi-machine job.

    ``job_id`` itself is returned when it already is that machine. A plain single-machine
    replica has no other machines to select, so anything but its own rank is an error.
    """
    job = JobApiV2().get_job(job_id, teamspace_id)
    if (getattr(job.spec, "rank", 0) or 0) == rank:
        return job.id

    parent_id = getattr(job, "multi_machine_job_id", None)
    if not parent_id:
        raise click.ClickException(f"--rank {rank}: this replica is a single machine. Read it without --rank.")
    for subjob in sorted(MMTApiV2().list_mmt_subjobs(parent_id, teamspace_id), key=lambda s: s.spec.rank):
        if subjob.spec.rank == rank:
            return subjob.id
    raise click.ClickException(f"--rank {rank} is out of range; the multi-machine job has fewer machines.")


@click.command("download", cls=LightningCommand)
@click.argument("name")
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace).")
@click.option("--job-id", "job_ids", multiple=True, help="Specific deployment job ID. Can be repeated.")
@click.option("--timestamps", is_flag=True, default=False, help="Prepend each line with its ISO-8601 timestamp.")
def download_deployment(
    name: str,
    teamspace: Optional[str] = None,
    job_ids: Sequence[str] = (),
    timestamps: bool = False,
) -> None:
    """Download the complete logs for a deployment replica."""
    resolved_teamspace = resolve_teamspace(teamspace)
    api = DeploymentApi()
    deployment = resolve_deployment(api, resolved_teamspace.id, name)

    from lightning_sdk.deployment import Deployment

    resource = Deployment(name=deployment.name, teamspace=resolved_teamspace)
    run_download(
        resource,
        timestamps=timestamps,
        job_id=job_ids[0] if job_ids else None,
    )


deployment_logs = make_logs_group(
    default_cmd=_deployment_logs_cmd,
    download_cmd=download_deployment,
    help_text="View the logs for a deployment.",
)
