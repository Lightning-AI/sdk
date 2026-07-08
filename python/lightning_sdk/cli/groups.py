"""CLI groups for organizing Lightning SDK commands."""

import rich_click as click

from lightning_sdk.cli.api import APIGroup
from lightning_sdk.cli.api import register_commands as register_api_commands
from lightning_sdk.cli.api_key import register_commands as register_api_key_commands
from lightning_sdk.cli.base_studio import register_commands as register_base_studio_commands
from lightning_sdk.cli.config import register_commands as register_config_commands
from lightning_sdk.cli.container import register_commands as register_container_commands
from lightning_sdk.cli.cp import register_commands as register_cp_commands
from lightning_sdk.cli.dataset import register_commands as register_dataset_commands
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
from lightning_sdk.cli.utils.logging import LightningCommand, LightningGroup


@click.group(name="studio", cls=LightningGroup)
def studio() -> None:
    """Persistent GPU dev workspaces."""


@click.group(name="job", cls=LightningGroup)
def job() -> None:
    """Run batch jobs and sweeps."""


@click.group(name="mmt", cls=LightningGroup)
def mmt() -> None:
    """Multi-node distributed training."""


@click.group(name="machine", cls=LightningGroup)
def machine() -> None:
    """Browse GPU and CPU machine types."""


@click.group(name="config", cls=LightningGroup)
def config() -> None:
    """Manage SDK and CLI settings."""


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


@click.group(name="deployment", cls=LightningGroup)
def deployment() -> None:
    """Deploy autoscaling inference APIs."""


@click.group(name="sandbox", cls=LightningGroup)
def sandbox() -> None:
    """Ephemeral sandboxes for agents.

    Set LIGHTNING_SANDBOX_API_KEY for non-interactive authentication. The sandbox
    API uses https://lightning.ai by default; set LIGHTNING_CLOUD_URL to override
    the host.

    Examples:
      $ sandbox list --teamspace owner/teamspace --limit 2
      ┏━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
      ┃ ID     ┃ Name   ┃ Status  ┃ Instance type ┃ Persistent ┃
      ┡━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
      │ sbx-42 │ devbox │ running │ cpu-1         │ yes        │
      └────────┴────────┴─────────┴───────────────┴────────────┘

      $ sandbox create --name devbox --teamspace owner/teamspace --persistent
      ┏━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┓
      ┃ ID     ┃ Name   ┃ Status  ┃ Instance type ┃ Persistent ┃ Cluster   ┃
      ┡━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━┩
      │ sbx-42 │ devbox │ running │ cpu-1         │ yes        │ aws-use1  │
      └────────┴────────┴─────────┴───────────────┴────────────┴───────────┘

      $ sandbox run sbx-42 -- python -c "print('hello')"
      hello

      $ sandbox run sbx-42 --detached -- bash -lc "echo start; sleep 1; echo done"
      cmd-abc123

      $ sandbox logs sbx-42 cmd-abc123 --no-timestamps
      start
      done

      $ sandbox stop sbx-42
      Stopped sandbox sbx-42
      Auto snapshot: snap-abc123
    """


@click.group(name="container", cls=LightningGroup)
def container() -> None:
    """Run and manage containers."""


@click.group(name="model", cls=LightningGroup)
def model() -> None:
    """Register and version models."""


@click.group(name="api-key", cls=LightningGroup)
def api_key() -> None:
    """Keys for model endpoint access.

    Org context is inferred automatically. If you use multiple orgs, set
    LIGHTNING_ORG or `lightning config set organization.name` to match the org
    selected in the web UI.
    """


@click.group(name="file", cls=LightningGroup)
def file() -> None:
    """Upload and download files."""


@click.group(name="folder", cls=LightningGroup)
def folder() -> None:
    """Upload and download folders."""


@click.group(name="ssh", cls=LightningGroup)
def ssh() -> None:
    """Configure SSH access to Studios."""


@click.group(name="base-studio", cls=LightningGroup)
def base_studio() -> None:
    """Reusable Studio environment images."""


@click.group(name="license", cls=LightningGroup)
def license() -> None:  # noqa: A001
    """View and manage product licenses."""


@click.group(name="dataset", cls=LightningGroup)
def dataset() -> None:
    """Upload and download datasets."""


@click.command(name="cp", cls=LightningCommand)
@click.argument("source")
@click.argument("destination", required=False)
@click.option("--recursive", "-r", is_flag=True, help="Copy directories recursively")
@click.pass_context
def cp() -> None:
    """Copy between local, Studios, Drive.

    URL formats:
      Studios:          lit://<owner>/<teamspace>/studios/<studio-name>/<path>
      Teamspace drives: lit://<owner>/<teamspace>/uploads/<path>

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
register_sandbox_commands(sandbox)
register_container_commands(container)
register_model_commands(model)
register_api_key_commands(api_key)
register_file_commands(file)
register_folder_commands(folder)
register_ssh_commands(ssh)
register_base_studio_commands(base_studio)
register_license_commands(license)
register_dataset_commands(dataset)
register_cp_commands(cp)
