"""Job SSH command."""

import subprocess
from typing import Optional

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_job, resolve_mmt, resolve_teamspace
from lightning_sdk.cli.utils.ssh_connection import configure_ssh_internal
from lightning_sdk.job import Job
from lightning_sdk.mmt import MMT
from lightning_sdk.status import Status
from lightning_sdk.teamspace import Teamspace

_SSH_HOST = "ssh.lightning.ai"
_JOB_ID_PREFIX = "job_"


def _ssh_user_for_job_id(job_id: str) -> str:
    """Map a stored job id (``job_<ulid>``) to the SSH gateway user (``j_<ulid>``)."""
    suffix = job_id[len(_JOB_ID_PREFIX) :] if job_id.startswith(_JOB_ID_PREFIX) else job_id
    return f"j_{suffix}"


def _machine_for_rank(mmt: MMT, rank: int) -> Job:
    machines = mmt.machines
    if not machines:
        raise click.ClickException(f"Multi-machine job '{mmt.name}' has no machines to SSH into.")

    expected = f"{mmt.name}-{rank}"
    for machine in machines:
        if machine.name == expected:
            return machine

    prefix = f"{mmt.name}-"
    available_ranks = sorted(
        int(suffix)
        for machine in machines
        if machine.name.startswith(prefix) and (suffix := machine.name[len(prefix) :]).isdigit()
    )
    available = ", ".join(str(r) for r in available_ranks)
    raise click.ClickException(
        f"Rank {rank} not found on multi-machine job '{mmt.name}'. Available ranks: {available or 'none'}."
    )


def _resolve_ssh_target(name: str, teamspace: Teamspace, rank: Optional[int]) -> Job:
    """Resolve a job name, or an MMT name (+ optional ``--rank``) to a single Job."""
    try:
        job = resolve_job(name, teamspace)
    except click.UsageError:
        job = None

    if job is not None:
        if rank is not None:
            click.echo(
                f"Note: '{name}' resolved as a single job; ignoring --rank {rank}.",
                err=True,
            )
        return job

    try:
        mmt = resolve_mmt(name, teamspace)
    except click.UsageError as ex:
        raise click.ClickException(
            f"Could not resolve job or multi-machine job '{name}' in teamspace '{teamspace.name}'."
        ) from ex

    selected_rank = 0 if rank is None else rank
    return _machine_for_rank(mmt, selected_rank)


@click.command("ssh", cls=LightningCommand)
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
@click.option(
    "--rank",
    type=int,
    default=None,
    help="Machine rank for a multi-machine job. Defaults to 0.",
)
def ssh_job(
    name: str,
    teamspace: Optional[str] = None,
    rank: Optional[int] = None,
) -> None:
    """SSH into a running job.

    For multi-machine jobs, use ``--rank`` to choose a machine (defaults to 0).

    Example:
        lightning job ssh my-job
        lightning job ssh my-distributed-job --rank 1
    """
    ssh_impl(name=name, teamspace=teamspace, rank=rank)


def ssh_impl(
    name: Optional[str],
    teamspace: Optional[str],
    rank: Optional[int] = None,
) -> None:
    if not name:
        raise click.UsageError("Missing job name. Pass NAME.")

    resolved_teamspace = resolve_teamspace(teamspace)
    job = _resolve_ssh_target(name, resolved_teamspace, rank)

    if job.status != Status.Running:
        raise click.ClickException(
            f"Job '{job.name}' is {job.status}, not Running. SSH is only available while the job is running."
        )

    job_id = job.id
    if not job_id:
        raise click.ClickException(f"Could not resolve id for job '{job.name}'.")

    ssh_user = _ssh_user_for_job_id(job_id)

    def _run(key_path: str) -> None:
        command = f"ssh -i {key_path} {ssh_user}@{_SSH_HOST}"
        subprocess.run(command.split())

    try:
        _run(configure_ssh_internal())
    except Exception:
        # Redownload keys in case they are stale, then retry once.
        try:
            _run(configure_ssh_internal(force_download=True))
        except Exception:
            raise click.ClickException("Failed to establish SSH connection") from None
