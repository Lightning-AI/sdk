"""Cloud instance (plain VM) command implementations."""

from __future__ import annotations

import shlex
import subprocess
from collections.abc import Sequence

import rich_click as click
from rich.console import Console
from rich.table import Table

from lightning_sdk.cli.resource_completion import complete_instance, complete_organization
from lightning_sdk.cli.utils.delete import DeleteAction
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cloud_instance import CloudInstance

_ORG_OPTION = click.option(
    "--org",
    default=None,
    help="The organization owning the instance. Defaults to the current organization.",
    shell_complete=complete_organization,
)


def _instance_row(instance: CloudInstance) -> list[str]:
    data = instance.to_dict()
    return [
        data["id"],
        data["name"],
        data["status"],
        data["instance_type"],
        data["cloud_account"],
        ",".join(str(port) for port in data["ports"]) or "-",
        "yes" if data["spot"] else "no",
    ]


def _instance_table(instances: Sequence[CloudInstance]) -> Table:
    table = Table(pad_edge=True)
    for column in ("ID", "Name", "Status", "Instance type", "Cloud account", "Ports", "Spot"):
        table.add_column(column, no_wrap=True)
    for instance in instances:
        table.add_row(*_instance_row(instance))
    return table


def _echo_instance(instance: CloudInstance, as_json: bool) -> None:
    if as_json:
        echo_json(instance.to_dict())
        return

    console = Console()
    console.print(_instance_table([instance]))
    data = instance.to_dict()
    if data["ssh_command"]:
        console.print(f"\nSSH  {data['ssh_command']}")
    elif data["status_reason"]:
        console.print(f"\nReason  {data['status_reason']}")


def resolve_instance_delete(name_or_id: str, org: str | None) -> DeleteAction:
    """Resolve an instance and return its bound deletion action."""
    return CloudInstance(name_or_id, org=org).delete


@click.command("create", cls=LightningCommand)
@click.argument("name")
@click.option(
    "--instance-type",
    "-t",
    required=True,
    help="The machine type to provision, e.g. cpu-4. See `lightning instance types`.",
)
@click.option(
    "--cloud-account",
    default=None,
    help="The cloud account to create the instance on. Defaults to the only one able to host instances.",
)
@_ORG_OPTION
@click.option("--volume-size", type=int, default=None, help="Root volume size in GB.")
@click.option("--spot", is_flag=True, default=False, help="Request an interruptible (spot) instance.")
@click.option(
    "--port",
    "ports",
    type=int,
    multiple=True,
    help="Port to expose on the instance, in addition to SSH. Can be specified multiple times.",
)
@click.option("--image", default=None, help="Curated image to boot from. See `lightning instance images`.")
@click.option(
    "--cloud-init",
    type=click.Path(exists=True, dir_okay=False, allow_dash=True),
    default=None,
    help="Path to a #cloud-config file to apply at boot. Use - to read from stdin.",
)
@click.option("--wait", is_flag=True, default=False, help="Block until the instance is running.")
@click.option("--timeout", type=float, default=900, help="Seconds to wait for the instance when --wait is set.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def create_instance(
    name: str,
    instance_type: str,
    cloud_account: str | None = None,
    org: str | None = None,
    volume_size: int | None = None,
    spot: bool = False,
    ports: Sequence[int] = (),
    image: str | None = None,
    cloud_init: str | None = None,
    wait: bool = False,
    timeout: float = 900,
    as_json: bool = False,
) -> None:
    """Create a cloud instance.

    An instance is a raw VM: Lightning provisions it, injects your account's SSH keys
    and gets out of the way.

    Example:
      $ lightning instance create my-vm -t cpu-4 --port 8080 --wait
    """
    # click.open_file reads stdin for "-", so both file and piped configs land here.
    cloud_init_content = click.open_file(cloud_init).read() if cloud_init is not None else None

    instance = CloudInstance.create(
        name=name,
        instance_type=instance_type,
        cloud_account=cloud_account,
        org=org,
        volume_size=volume_size,
        spot=spot,
        ports=list(ports),
        image=image,
        cloud_init=cloud_init_content,
        wait=wait,
        timeout=timeout,
    )
    _echo_instance(instance, as_json)


@click.command("list", cls=LightningCommand)
@_ORG_OPTION
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_instances(org: str | None = None, as_json: bool = False) -> None:
    """List the cloud instances of an organization.

    Example:
      $ lightning instance list
    """
    instances = CloudInstance.list(org=org)

    if as_json:
        echo_json([instance.to_dict() for instance in instances])
        return

    if not instances:
        click.echo("No instances found")
        return

    Console().print(_instance_table(instances))


@click.command("get", cls=LightningCommand)
@click.argument("name_or_id", shell_complete=complete_instance)
@_ORG_OPTION
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def get_instance(name_or_id: str, org: str | None = None, as_json: bool = False) -> None:
    """Show a single cloud instance.

    Example:
      $ lightning instance get 01k0abc
    """
    _echo_instance(CloudInstance(name_or_id, org=org), as_json)


@click.command("images", cls=LightningCommand)
@click.option("--cloud-account", default=None, help="Restrict the images to a single cloud account.")
@_ORG_OPTION
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_instance_images(
    cloud_account: str | None = None,
    org: str | None = None,
    as_json: bool = False,
) -> None:
    """List the images cloud instances can boot from.

    The first image is the default one used when `--image` is not passed to create.

    Example:
      $ lightning instance images
    """
    images = CloudInstance.images(cloud_account=cloud_account, org=org)

    if as_json:
        echo_json([{"name": image.name, "description": image.description} for image in images])
        return

    if not images:
        click.echo("No images found")
        return

    table = Table(pad_edge=True)
    table.add_column("Name", no_wrap=True)
    table.add_column("Description")
    for image in images:
        table.add_row(image.name, image.description)
    Console().print(table)


@click.command("types", cls=LightningCommand)
@click.option("--cloud-account", default=None, help="The cloud account to list machine types of.")
@_ORG_OPTION
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_instance_types(
    cloud_account: str | None = None,
    org: str | None = None,
    as_json: bool = False,
) -> None:
    """List the machine types cloud instances can run on, cheapest first.

    Example:
      $ lightning instance types
    """
    types = CloudInstance.instance_types(cloud_account=cloud_account, org=org)

    if as_json:
        echo_json([{"name": t.name, "description": t.description, "cost_per_hour": t.cost} for t in types])
        return

    if not types:
        click.echo("No machine types found")
        return

    table = Table(pad_edge=True)
    table.add_column("Name", no_wrap=True)
    table.add_column("Resources")
    table.add_column("USD / hour", justify="right", no_wrap=True)
    for instance_type in types:
        table.add_row(instance_type.name, instance_type.description, f"{instance_type.cost:.2f}")
    Console().print(table)


@click.command(
    "ssh",
    cls=LightningCommand,
    context_settings={"ignore_unknown_options": True},
)
@click.argument("name_or_id", shell_complete=complete_instance)
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
@_ORG_OPTION
@click.option(
    "--option",
    "-o",
    "options",
    multiple=True,
    help="Additional options to pass to the SSH command. Can be specified multiple times.",
)
@click.option(
    "--identity",
    "-i",
    "key_path",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Private key to authenticate with. Defaults to the Lightning-managed key.",
)
@click.option("--print", "print_only", is_flag=True, default=False, help="Print the SSH command instead of running it.")
def ssh_instance(
    name_or_id: str,
    command: Sequence[str] = (),
    org: str | None = None,
    options: Sequence[str] = (),
    key_path: str | None = None,
    print_only: bool = False,
) -> None:
    """SSH into a cloud instance, or run a single command on it.

    Examples:
      $ lightning instance ssh my-vm
      $ lightning instance ssh my-vm -- uname -a
      $ lightning instance ssh my-vm -i ~/.ssh/id_ed25519 -- uname -a
    """
    instance = CloudInstance(name_or_id, org=org)
    args = instance.ssh_args(command=list(command), options=list(options), key_path=key_path)

    if print_only:
        click.echo(shlex.join(args))
        return

    raise SystemExit(subprocess.run(args, check=False).returncode)
