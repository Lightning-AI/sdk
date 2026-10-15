"""Job watch command: live progress, ETA and setbacks for a job."""

import sys
from pathlib import Path
from typing import Any, Dict, Optional

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_job, resolve_teamspace


@click.command("watch", cls=LightningCommand)
@click.argument("name", help="The job name.")
@click.option(
    "--teamspace",
    default=None,
    help="Teamspace owner/name. Uses the configured default teamspace when omitted.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Print one JSON object per line: every event, plus the run's state whenever it changes.",
)
@click.option(
    "--state-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Folder for the run's state and events. Defaults to $LIGHTNING_PROGRESS_DIR, else "
    "$XDG_STATE_HOME/lightning-progress, else ~/.local/state/lightning-progress.",
)
@click.option("--run", "run_name", default=None, help="Run to continue, e.g. with a relaunched job.")
@click.option("--note", default=None, help="Why this job was (re)launched, kept in the run's history.")
@click.option(
    "--query",
    default=None,
    help="Server-side log filter, e.g. PROGRESS for very chatty jobs (hides error lines from stall causes).",
)
@click.option(
    "--relaunch-wait",
    type=click.FloatRange(min=0),
    default=0.0,
    show_default=True,
    help="Seconds a failed run waits for a relaunch (`--run`) before it is final.",
)
def watch_job(
    name: str,
    teamspace: Optional[str] = None,
    as_json: bool = False,
    state_dir: Optional[Path] = None,
    run_name: Optional[str] = None,
    note: Optional[str] = None,
    query: Optional[str] = None,
    relaunch_wait: float = 0.0,
) -> None:
    """Follow a job's progress live, with an ETA, until it ends.

    The job reports progress by printing `PROGRESS <step>/<total>` lines (tqdm bars are a
    fallback) and can name its stages with `PROGRESS_PHASE <name> <i>/<n>`. Setbacks, such as a
    retry that resumes from a checkpoint, and stalls are reported as they happen.

    The run's state and events are also written to the state folder, for other tools to read.
    Watching a relaunched job with `--run RUN` continues that run's history; while RUN's watcher
    is still running, the job is handed to it instead.

    Exits 0 once the job completes, and 1 if it fails or is stopped.
    """
    from lightning_sdk.job import Job
    from lightning_sdk.utils.job_progress.render import JsonLinesOutput, TerminalOutput
    from lightning_sdk.utils.job_progress.store import default_state_dir
    from lightning_sdk.utils.job_progress.watch import JobWatcher

    resolved_teamspace = resolve_teamspace(teamspace)
    first = resolve_job(name, resolved_teamspace)
    slug = f"{resolved_teamspace.owner.name}/{resolved_teamspace.name}"
    cache: Dict[str, Any] = {name: first}

    def job_factory(job_name: str, job_teamspace: Optional[str]) -> Any:
        if job_name in cache and job_teamspace in (None, slug):
            return cache[job_name]
        return Job(job_name, teamspace=job_teamspace or resolved_teamspace)

    watcher = JobWatcher(
        name,
        teamspace=slug,
        teamspace_id=resolved_teamspace.id,
        state_dir=state_dir or default_state_dir(),
        output=JsonLinesOutput() if as_json else TerminalOutput(),
        job_factory=job_factory,
        run=run_name,
        note=note,
        query=query,
        relaunch_wait=relaunch_wait,
    )
    try:
        code = watcher.watch()
    except KeyboardInterrupt:
        code = 130
    sys.exit(code)
