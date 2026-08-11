"""MMT SSH command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_job_machine, resolve_mmt, resolve_teamspace
from lightning_sdk.cli.utils.ssh_connection import _job_ssh_user, exec_ssh
from lightning_sdk.status import Status


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
    job = resolve_job_machine(mmt, rank)

    if job.status != Status.Running:
        raise click.ClickException(
            f"Machine '{job.name}' is {job.status}, not Running. SSH is only available while the machine is running."
        )

    job_id = job.id
    if not job_id:
        raise click.ClickException(f"Could not resolve id for machine '{job.name}'.")

    ssh_user = _job_ssh_user(job_id)
    exec_ssh(ssh_user)
