"""CLI groups for organizing Lightning SDK commands."""

import click

from lightning_sdk.cli.config import register_commands as register_config_commands
from lightning_sdk.cli.job import register_commands as register_job_commands
from lightning_sdk.cli.mmt import register_commands as register_mmt_commands
from lightning_sdk.cli.studio import register_commands as register_studio_commands


@click.group(name="studio")
def studio() -> None:
    """Manage Lightning AI Studios."""


@click.group(name="job")
def job() -> None:
    """Manage Lightning AI Jobs."""


@click.group(name="mmt")
def mmt() -> None:
    """Manage Lightning AI Multi-Machine Training (MMT)."""


@click.group(name="config")
def config() -> None:
    """Manage Lightning SDK and CLIconfiguration."""


# Register config commands with the main config group
register_job_commands(job)
register_mmt_commands(mmt)
register_studio_commands(studio)
register_config_commands(config)
