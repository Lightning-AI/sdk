"""CLI groups for organizing Lightning SDK commands."""

import click

from lightning_sdk.cli.base_studio import register_commands as register_base_studio_commands
from lightning_sdk.cli.config import register_commands as register_config_commands
from lightning_sdk.cli.job import register_commands as register_job_commands
from lightning_sdk.cli.license import register_commands as register_license_commands
from lightning_sdk.cli.mmt import register_commands as register_mmt_commands
from lightning_sdk.cli.studio import register_commands as register_studio_commands
from lightning_sdk.cli.vm import register_commands as register_vm_commands


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
    """Manage Lightning SDK and CLI configuration."""


@click.group(name="vm")
def vm() -> None:
    """Manage Lightning AI VMs."""


@click.group(name="base-studio")
def base_studio() -> None:
    """Manage Lightning AI Base Studios."""


@click.group(name="license")
def license() -> None:  # noqa: A001
    """Manage Lightning AI Product Licenses."""


# Register config commands with the main config group
register_job_commands(job)
register_mmt_commands(mmt)
register_studio_commands(studio)
register_config_commands(config)
register_vm_commands(vm)
register_base_studio_commands(base_studio)
register_license_commands(license)
