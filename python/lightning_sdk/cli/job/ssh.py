"""Job SSH command."""

import subprocess
from typing import Optional

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_job, resolve_teamspace
from lightning_sdk.cli.utils.ssh_connection import configure_ssh_internal
from lightning_sdk.status import Status

_SSH_HOST = "ssh.lightning.ai"
_JOB_ID_PREFIX = "job_"


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
def ssh_job(
    name: str,
    teamspace: Optional[str] = None,
) -> None:
    """SSH into a running job.

    Example:
        lightning job ssh my-job
    """
    ssh_impl(name=name, teamspace=teamspace)


def ssh_impl(
    name: Optional[str],
    teamspace: Optional[str],
) -> None:
    if not name:
        raise click.UsageError("Missing job name. Pass NAME.")

    resolved_teamspace = resolve_teamspace(teamspace)
    job = resolve_job(name, resolved_teamspace)

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
