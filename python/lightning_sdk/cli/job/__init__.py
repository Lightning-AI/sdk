"""Job CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register job commands with the given group."""
    from lightning_sdk.cli.job.delete import delete_job
    from lightning_sdk.cli.job.inspect import inspect_job
    from lightning_sdk.cli.job.list import list_jobs
    from lightning_sdk.cli.job.run import run_job
    from lightning_sdk.cli.job.stop import stop_job

    group.add_command(run_job, name="run")
    group.add_command(list_jobs, name="list")
    group.add_command(inspect_job, name="inspect")
    group.add_command(stop_job, name="stop")
    group.add_command(delete_job, name="delete")
