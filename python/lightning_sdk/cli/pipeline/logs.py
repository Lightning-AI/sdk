"""Pipeline logs command."""

from contextlib import suppress
from typing import Optional

import rich_click as click

from lightning_sdk.api.logs_api import SEVERITIES
from lightning_sdk.api.pipeline_api import PipelineApi
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.logs import (
    LogSelection,
    make_logs_group,
    read_logs,
    resolve_time,
    run_download,
)
from lightning_sdk.cli.utils.resource_resolution import (
    resolve_job_machine,
    resolve_teamspace,
)
from lightning_sdk.job import Job
from lightning_sdk.lightning_cloud.openapi import V1Pipeline, V1PipelineStepStatus
from lightning_sdk.teamspace import Teamspace


def _resolve_pipeline_step(
    pipeline_obj: V1Pipeline,
    step_name: str,
    teamspace: Teamspace,
) -> Job:
    """Find a pipeline step by name."""
    if not pipeline_obj.statuses:
        raise click.ClickException(f"No steps found for pipeline '{pipeline_obj.name}'. Has the pipeline been run?")

    for status in pipeline_obj.statuses:
        if status.name == step_name:
            return _job_from_status(status, step_name, teamspace)

    available = ", ".join(s.name for s in pipeline_obj.statuses)
    raise click.ClickException(
        f"Step '{step_name}' not found in the current pipeline run. Available steps: {available or 'none'}"
    )


def _job_from_status(
    status: V1PipelineStepStatus,
    step_name: str,
    teamspace: Teamspace,
) -> Job:
    """Create a ``Job`` from a ``V1PipelineStepStatus`` entry."""
    from lightning_sdk.api.utils import cached_lightning_client
    from lightning_sdk.lightning_cloud.openapi.rest import ApiException

    resource_id = status.resource_id
    if not resource_id:
        raise click.ClickException(
            f"Step '{step_name}' has no resource_id in its status. "
            f"The pipeline run may not have started the step yet."
        )

    client = cached_lightning_client(retry=False)
    try:
        job_payload = client.jobs_service_get_job(project_id=teamspace.id, id=resource_id)
    except ApiException as ex:
        if ex.status == 404:
            raise click.ClickException(
                f"Step '{step_name}' resolves to resource_id "
                f"'{resource_id}' but the job no longer exists. "
                f"It may have been deleted."
            ) from ex
        raise click.ClickException(
            f"Failed to fetch job for step '{step_name}' (resource_id={resource_id}): {ex}"
        ) from ex
    except Exception as ex:
        raise click.ClickException(
            f"Failed to fetch job for step '{step_name}' (resource_id={resource_id}): {ex}"
        ) from ex

    job = Job(name=step_name, teamspace=teamspace, _fetch_job=False)
    job._attach_job(job_payload)
    return job


@click.command("logs", cls=LightningCommand)
@click.argument("pipeline", required=False, help="The pipeline name. Required.")
@click.argument("step", required=False, help="The step (job) name within the pipeline. Required.")
@click.option(
    "--teamspace",
    default=None,
    help=("Teamspace owner/name. Uses the configured default teamspace when omitted."),
)
@click.option(
    "--follow",
    "-f",
    is_flag=True,
    default=False,
    help="Stream new log lines as they are produced.",
)
@click.option(
    "--tail",
    type=int,
    default=None,
    help="Only show the last N lines.",
)
@click.option(
    "--rank",
    type=int,
    default=None,
    help="Machine rank to read from in a multi-machine job.",
)
@click.option(
    "--timestamps",
    is_flag=True,
    default=False,
    help="Prepend each line with its ISO-8601 timestamp.",
)
@click.option(
    "--since",
    default=None,
    help='Only include lines at or after this time (e.g. "2h", RFC3339).',
)
@click.option(
    "--until",
    default=None,
    help='Only include lines at or before this time (e.g. "30m", RFC3339).',
)
@click.option(
    "--query",
    default=None,
    help="Only include lines containing every whitespace-separated term.",
)
@click.option(
    "--severity",
    type=click.Choice(SEVERITIES),
    default=None,
    help="Only include lines at or above this severity.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Output entries as a JSON array.",
)
@click.option(
    "--interactive",
    "-i",
    "tui",
    is_flag=True,
    default=False,
    help="Launch the interactive TUI log viewer.",
)
def _logs_pipeline_cmd(
    pipeline: Optional[str] = None,
    step: Optional[str] = None,
    teamspace: Optional[str] = None,
    follow: bool = False,
    tail: Optional[int] = None,
    rank: Optional[int] = None,
    timestamps: bool = False,
    since: Optional[str] = None,
    until: Optional[str] = None,
    query: Optional[str] = None,
    severity: Optional[str] = None,
    as_json: bool = False,
    tui: bool = False,
) -> None:
    """Print the logs for a pipeline step.

    Pipeline steps are backed by jobs. This command resolves the pipeline by
    name and the step within it, then prints the step's logs using the same
    options as ``lightning job logs``.
    """
    resolved_teamspace = resolve_teamspace(teamspace)

    if not pipeline:
        raise click.UsageError("Missing pipeline name. Pass PIPELINE.")
    if not step:
        raise click.UsageError("Missing step name. Pass STEP.")

    pipeline_api = PipelineApi()
    pipeline_obj = pipeline_api.get_pipeline_by_id(resolved_teamspace.id, pipeline)
    if pipeline_obj is None:
        raise click.ClickException(f"Could not resolve pipeline '{pipeline}' in teamspace '{resolved_teamspace.name}'.")

    job = _resolve_pipeline_step(pipeline_obj, step, resolved_teamspace)

    selected_rank = job.is_multi_machine is True and rank is not None

    if selected_rank:
        assert rank is not None
        job = resolve_job_machine(job, rank)

    if tui:
        from lightning_sdk.cli.logs_tui import run_tui

        assert job.resource_id is not None, "job must have a resource_id"
        run_tui(
            LogSelection(
                teamspace_id=resolved_teamspace.id,
                job_ids=[job.resource_id],
            ),
            follow=(follow or (since is None and until is None)),
            tail=tail,
            show_timestamps=True,
            since=since,
            until=until,
            query=query,
            title=(f"{resolved_teamspace.owner.name}/{resolved_teamspace.name}/{pipeline}/{step} logs"),
        )
        return

    if as_json:
        if rank is not None and not selected_rank:
            raise click.ClickException("--rank is not supported with --json.")
        if job.is_multi_machine is True:
            labels: dict = {}
            with suppress(Exception):
                labels = {
                    machine.resource_id: machine.name for machine in job.machines if machine.resource_id is not None
                }
            selection = LogSelection(
                teamspace_id=resolved_teamspace.id,
                mmt_id=job.resource_id,
                labels=labels,
            )
        else:
            if job.resource_id is None:
                raise click.ClickException("The selected job does not have a resource ID.")
            selection = LogSelection(
                teamspace_id=resolved_teamspace.id,
                job_ids=[job.resource_id],
            )
        read_logs(
            selection,
            query=query,
            severity=severity,
            since=resolve_time(since, "--since"),
            until=resolve_time(until, "--until"),
            tail=tail,
            follow=follow,
            as_json=True,
        )
        return

    try:
        if job.is_multi_machine is True:
            logs = job.logs(
                follow=follow,
                tail=tail,
                timestamps=timestamps,
                since=resolve_time(since, "--since"),
                until=resolve_time(until, "--until"),
                query=query,
                severity=severity,
            )
        else:
            logs = job.logs(
                follow=follow,
                tail=tail,
                rank=0 if selected_rank else rank,
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


@click.command("download", cls=LightningCommand)
@click.argument("pipeline", required=False, help="The pipeline name. Required.")
@click.argument("step", required=False, help="The step (job) name within the pipeline. Required.")
@click.option(
    "--teamspace",
    default=None,
    help=("Teamspace owner/name. Uses the configured default teamspace when omitted."),
)
@click.option("--timestamps", is_flag=True, default=False, help="Prepend each line with its ISO-8601 timestamp.")
def download_pipeline(
    pipeline: Optional[str] = None,
    step: Optional[str] = None,
    teamspace: Optional[str] = None,
    timestamps: bool = False,
) -> None:
    """Download the complete logs for a pipeline step."""
    resolved_teamspace = resolve_teamspace(teamspace)

    if not pipeline:
        raise click.UsageError("Missing pipeline name. Pass PIPELINE.")
    if not step:
        raise click.UsageError("Missing step name. Pass STEP.")

    pipeline_api = PipelineApi()
    pipeline_obj = pipeline_api.get_pipeline_by_id(resolved_teamspace.id, pipeline)
    if pipeline_obj is None:
        raise click.ClickException(f"Could not resolve pipeline '{pipeline}' in teamspace '{resolved_teamspace.name}'.")

    job = _resolve_pipeline_step(pipeline_obj, step, resolved_teamspace)
    run_download(job, timestamps=timestamps)


logs_pipeline = make_logs_group(
    default_cmd=_logs_pipeline_cmd,
    download_cmd=download_pipeline,
    help_text="View the logs for a pipeline step.",
)
