"""CLI groups for organizing Lightning SDK commands."""

import click

from lightning_sdk.cli.api import APIGroup
from lightning_sdk.cli.api import register_commands as register_api_commands
from lightning_sdk.cli.api_key import register_commands as register_api_key_commands
from lightning_sdk.cli.base_studio import register_commands as register_base_studio_commands
from lightning_sdk.cli.config import register_commands as register_config_commands
from lightning_sdk.cli.container import register_commands as register_container_commands
from lightning_sdk.cli.cp import register_commands as register_cp_commands
from lightning_sdk.cli.deployment import register_commands as register_deployment_commands
from lightning_sdk.cli.file import register_commands as register_file_commands
from lightning_sdk.cli.folder import register_commands as register_folder_commands
from lightning_sdk.cli.job import register_commands as register_job_commands
from lightning_sdk.cli.license import register_commands as register_license_commands
from lightning_sdk.cli.machine import register_commands as register_machine_commands
from lightning_sdk.cli.mmt import register_commands as register_mmt_commands
from lightning_sdk.cli.model import register_commands as register_model_commands
from lightning_sdk.cli.sandbox import register_commands as register_sandbox_commands
from lightning_sdk.cli.ssh import register_commands as register_ssh_commands
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


@click.group(name="machine")
def machine() -> None:
    """Manage Lightning AI machine types."""


@click.group(name="config")
def config() -> None:
    """Manage Lightning SDK and CLI configuration."""


@click.group(
    name="api",
    cls=APIGroup,
    hidden=True,
    invoke_without_command=True,
    no_args_is_help=False,
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.pass_context
def api(ctx: click.Context) -> None:
    """Manage Lightning AI APIs.

    Use `lightning api /path [options]` to make an authenticated raw HTTP request.
    """
    if ctx.invoked_subcommand is None and not ctx.args:
        click.echo(ctx.get_help())
        ctx.exit()


@click.group(name="deployment")
def deployment() -> None:
    """Manage Lightning AI Deployments."""


@click.group(name="vm")
def vm() -> None:
    """Manage Lightning AI VMs."""


@click.group(name="sandbox")
def sandbox() -> None:
    """Manage Lightning AI Sandboxes.

    The sandbox API uses https://lightning.ai by default. To override the host
    for development, set LIGHTNING_CLOUD_URL. Set LIGHTNING_SANDBOX_API_KEY and,
    when needed, LIGHTNING_ORG_ID for non-interactive authentication.

    \b
    Examples:
      $ sandbox list --teamspace owner/teamspace --limit 2
      ┏━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
      ┃ ID     ┃ Name   ┃ Status  ┃ Instance type ┃ Persistent ┃
      ┡━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
      │ sbx-42 │ devbox │ running │ cpu-small     │ yes        │
      └────────┴────────┴─────────┴───────────────┴────────────┘

    \b
      $ sandbox create --name devbox --teamspace owner/teamspace --persistent
      ┏━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┓
      ┃ ID     ┃ Name   ┃ Status  ┃ Instance type ┃ Persistent ┃ Cluster   ┃
      ┡━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━┩
      │ sbx-42 │ devbox │ running │ cpu-small     │ yes        │ aws-use1  │
      └────────┴────────┴─────────┴───────────────┴────────────┴───────────┘

    \b
      $ sandbox run sbx-42 -- python -c "print('hello')"
      hello

    \b
      $ sandbox run sbx-42 --detached -- bash -lc "echo start; sleep 1; echo done"
      cmd-abc123

    \b
      $ sandbox logs sbx-42 cmd-abc123 --no-timestamps
      start
      done

    \b
      $ sandbox stop sbx-42
      Stopped sandbox sbx-42
      Auto snapshot: snap-abc123
    """


@click.group(name="container")
def container() -> None:
    """Manage Lightning AI containers."""


@click.group(name="model")
def model() -> None:
    """Manage Lightning AI Models."""


@click.group(name="api-key")
def api_key() -> None:
    """Manage API keys for public model endpoints.

    Org context is inferred automatically. If you use multiple orgs, set
    LIGHTNING_ORG or `lightning config set organization.name` to match the org
    selected in the web UI.
    """


@click.group(name="file")
def file() -> None:
    """Manage file transfers."""


@click.group(name="folder")
def folder() -> None:
    """Manage folder transfers."""


@click.group(name="ssh")
def ssh() -> None:
    """Manage SSH configuration."""


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
      lightning cp source.txt lit://<owner>/<my-teamspace>/studios/<my-studio>/destination.txt
      lightning cp -r source_folder/ lit://<owner>/<my-teamspace>/studios/<my-studio>/destination_folder/
    """


# Register config commands with the main config group
register_job_commands(job)
register_mmt_commands(mmt)
register_machine_commands(machine)
register_studio_commands(studio)
register_config_commands(config)
register_api_commands(api)
register_deployment_commands(deployment)
register_vm_commands(vm)
register_sandbox_commands(sandbox)
register_container_commands(container)
register_model_commands(model)
register_api_key_commands(api_key)
register_file_commands(file)
register_folder_commands(folder)
register_ssh_commands(ssh)
register_base_studio_commands(base_studio)
register_license_commands(license)
register_cp_commands(cp)
