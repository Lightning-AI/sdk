"""MMT logs command."""

from typing import Optional

import rich_click as click

from lightning_sdk.api.logs_api import SEVERITIES
from lightning_sdk.cli.legacy.job_and_mmt_action import _JobAndMMTAction
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.logs import resolve_time


@click.command("logs", cls=LightningCommand)
@click.argument("name", required=False)
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the name of the teamspace the multi-machine job lives in. "
        "Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace). "
        "If not specified can be selected interactively."
    ),
)
@click.option("--follow", "-f", is_flag=True, default=False, help="Stream new log lines as they are produced.")
@click.option("--tail", type=int, default=None, help="Only show the last N lines.")
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
def logs_mmt(
    name: Optional[str] = None,
    teamspace: Optional[str] = None,
    follow: bool = False,
    tail: Optional[int] = None,
    timestamps: bool = False,
    since: Optional[str] = None,
    until: Optional[str] = None,
    query: Optional[str] = None,
    severity: Optional[str] = None,
) -> None:
    """Print the logs for a multi-machine job.

    Reads every machine, merged into one timeline and labelled with the machine each line came
    from. Pass --follow to stream new lines until the job finishes or you press Ctrl-C. To read a
    single machine, use `lightning job logs <machine-name>`.
    """
    mmt = _JobAndMMTAction().mmt(name=name, teamspace=teamspace)

    try:
        logs = mmt.logs(
            follow=follow,
            tail=tail,
            timestamps=timestamps,
            since=resolve_time(since, "--since"),
            until=resolve_time(until, "--until"),
            query=query,
            severity=severity,
        )
        if follow:
            for line in logs:
                click.echo(line)
        elif logs:
            click.echo(logs)
    except KeyboardInterrupt:
        pass
    except RuntimeError as ex:
        raise click.ClickException(str(ex)) from ex
