"""CLI groups for organizing Lightning SDK commands."""

import click

from lightning_sdk.cli.base_studio import register_commands as register_base_studio_commands
from lightning_sdk.cli.config import register_commands as register_config_commands
from lightning_sdk.cli.cp import register_commands as register_cp_commands
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


@click.command(name="cp")
@click.argument("source")
@click.argument("destination", required=False)
@click.option("--recursive", "-r", is_flag=True, help="Copy directories recursively")
@click.pass_context
def cp() -> None:
    """Copy files between local filesystem, Studios, and teamspace drives.

    \b
    URL formats:
      Studios:          lit://<owner>/<teamspace>/studios/<studio-name>/<path>
      Teamspace drives: lit://<owner>/<teamspace>/uploads/<path>

    \b
    Examples:
      lightning studio cp source.txt lit://<owner>/<my-teamspace>/studios/<my-studio>/destination.txt
      lightning studio cp -r source_folder/ lit://<owner>/<my-teamspace>/studios/<my-studio>/destination_folder/
    """


# Register config commands with the main config group
register_job_commands(job)
register_mmt_commands(mmt)
register_studio_commands(studio)
register_config_commands(config)
register_vm_commands(vm)
register_base_studio_commands(base_studio)
register_license_commands(license)
register_cp_commands(cp)
