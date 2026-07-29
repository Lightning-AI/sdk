"""MMT SSH command."""

import subprocess
from typing import Optional

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_mmt, resolve_teamspace
from lightning_sdk.cli.utils.ssh_connection import configure_ssh_internal
from lightning_sdk.job import Job
from lightning_sdk.mmt import MMT
from lightning_sdk.status import Status

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
    available_ranks = []
    for machine in machines:
        if not machine.name.startswith(prefix):
            continue
        suffix = machine.name[len(prefix) :]
        if suffix.isdigit():
            available_ranks.append(int(suffix))
    available = ", ".join(str(r) for r in sorted(available_ranks))
    raise click.ClickException(
        f"Rank {rank} not found on multi-machine job '{mmt.name}'. Available ranks: {available or 'none'}."
    )


@click.command("ssh", cls=LightningCommand)
@click.argument("name")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the name of the teamspace the multi-machine job lives in. "
        "Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace). "
        "If not specified, uses the configured default teamspace."
    ),
)
@click.option(
    "--rank",
    type=int,
    default=0,
    help="Machine rank to SSH into. Defaults to 0.",
)
def ssh_mmt(
    name: str,
    teamspace: Optional[str] = None,
    rank: int = 0,
) -> None:
    """SSH into a running multi-machine job.

    Example:
        lightning mmt ssh my-distributed-job
        lightning mmt ssh my-distributed-job --rank 1
    """
    ssh_impl(name=name, teamspace=teamspace, rank=rank)


def ssh_impl(
    name: str,
    teamspace: Optional[str],
    rank: int = 0,
) -> None:
    resolved_teamspace = resolve_teamspace(teamspace)
    mmt = resolve_mmt(name, resolved_teamspace)
    job = _machine_for_rank(mmt, rank)

    if job.status != Status.Running:
        raise click.ClickException(
            f"Machine '{job.name}' is {job.status}, not Running. SSH is only available while the machine is running."
        )

    job_id = job.id
    if not job_id:
        raise click.ClickException(f"Could not resolve id for machine '{job.name}'.")

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
