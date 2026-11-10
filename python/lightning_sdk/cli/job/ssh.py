"""Job SSH command."""

import subprocess
from typing import Optional

import rich_click as click

from lightning_sdk.cli.utils import lockdown_status
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_job, resolve_job_machine, resolve_teamspace
from lightning_sdk.cli.utils.ssh_connection import configure_ssh_internal
from lightning_sdk.status import Status

_SSH_HOST = "ssh.lightning.ai"
_JOB_ID_PREFIX = "job_"
# ssh exits with 255 when the connection fails, such as when the gateway refuses the login
_SSH_CONNECTION_FAILED = 255
_LOCKDOWN_SSH_HINT = (
    "While the API lockdown is on, only a Job's owner can SSH into it, "
    "and only into a single-machine Job that isn't part of a Deployment."
)


def _ssh_user_for_job_id(job_id: str) -> str:
    """Map a stored job id (``job_<ulid>``) to the SSH gateway user (``j_<ulid>``)."""
    suffix = job_id[len(_JOB_ID_PREFIX) :] if job_id.startswith(_JOB_ID_PREFIX) else job_id
    return f"j_{suffix}"


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
@click.option("--rank", type=int, default=None, help="Machine rank for a multi-machine job. Defaults to 0.")
def ssh_job(
    name: str,
    teamspace: Optional[str] = None,
    rank: Optional[int] = None,
) -> None:
    """SSH into a running job.

    Example:
        lightning job ssh my-job
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
    job = resolve_job(name, resolved_teamspace)
    if job.is_multi_machine is True:
        job = resolve_job_machine(job, rank if rank is not None else 0)
    elif rank is not None:
        raise click.UsageError("--rank is only supported for multi-machine jobs.")

    if job.status != Status.Running:
        raise click.ClickException(
            f"Job '{job.name}' is {job.status}, not Running. SSH is only available while the job is running."
        )

    job_id = job.id
    if not job_id:
        raise click.ClickException(f"Could not resolve id for job '{job.name}'.")

    ssh_user = _ssh_user_for_job_id(job_id)

    key_path = configure_ssh_internal()
    try:
        result = subprocess.run(f"ssh -i {key_path} {ssh_user}@{_SSH_HOST}".split())
    except OSError:
        raise click.ClickException("Failed to establish SSH connection") from None
    # The gateway shows no banner when it refuses a login, only ssh's own "Permission denied (publickey)".
    if result.returncode == _SSH_CONNECTION_FAILED and lockdown_status.lockdown_on():
        click.echo(_LOCKDOWN_SSH_HINT, err=True)
