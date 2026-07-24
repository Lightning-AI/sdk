"""Job logs command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.legacy.job_and_mmt_action import _JobAndMMTAction
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.status import Status

_TERMINAL = (Status.Completed, Status.Failed, Status.Stopped)


@click.command("logs", cls=LightningCommand)
@click.argument("name", required=False)
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the name of the teamspace the job lives in. "
        "Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace). "
        "If not specified can be selected interactively."
    ),
)
def logs_job(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Print the logs for a job.

    Logs are available once the job reaches a terminal state (Completed, Failed or
    Stopped). While the job is still pending or running this prints its current status
    instead of erroring — re-run once it has finished.
    """
    job = _JobAndMMTAction().job(name=name, teamspace=teamspace)
    if job.status not in _TERMINAL:
        raise click.ClickException(
            f"Job '{job.name}' is {job.status}; logs are only available once it reaches a "
            "terminal state (Completed/Failed/Stopped). Re-run this command after it finishes."
        )
    click.echo(job.logs)
