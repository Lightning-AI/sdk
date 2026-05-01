"""Studio start command."""

from typing import Optional

import click

from lightning_sdk.cli.utils.handle_machine_and_gpus_args import handle_machine_and_gpus_args
from lightning_sdk.cli.utils.richt_print import studio_name_link
from lightning_sdk.cli.utils.save_to_config import save_studio_to_config
from lightning_sdk.cli.utils.studio_selection import StudiosMenu
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.machine import CloudProvider, Machine
from lightning_sdk.studio import VM, Studio


@click.command("start")
@click.option(
    "--name",
    help=(
        "The name of the studio to start. "
        "If not provided, will try to infer from environment, "
        "use the default value from the config or prompt for interactive selection."
    ),
)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
@click.option("--create", is_flag=True, help="Create the studio if it doesn't exist")
@click.option(
    "--machine",
    help="The machine type to start the studio on. Defaults to CPU-4",
    type=click.Choice(m.name for m in Machine.__dict__.values() if isinstance(m, Machine) and m._include_in_cli),
)
@click.option("--interruptible", is_flag=True, help="Start the studio on an interruptible instance.")
@click.option(
    "--cloud-provider",
    help=(
        "The cloud provider to start the studio on. Defaults to teamspace default. Only used if --create is specified."
    ),
    type=click.Choice(m.name for m in list(CloudProvider)),
)
@click.option(
    "--cloud-account",
    help="The cloud account to start the studio on. Defaults to teamspace default. Only used if --create is specified.",
    type=click.STRING,
)
@click.option(
    "--gpus",
    help="The number and type of GPUs to start the studio on (format: TYPE:COUNT, e.g. L4:4)",
    type=click.STRING,
)
def start_studio(
    name: Optional[str] = None,
    teamspace: Optional[str] = None,
    create: bool = False,
    machine: str = "CPU",
    gpus: Optional[str] = None,
    interruptible: bool = False,
    cloud_provider: Optional[str] = None,
    cloud_account: Optional[str] = None,
) -> None:
    """Start a Studio.

    Example:
        lightning studio start --name my-studio

    """
    return start_impl(
        name=name,
        teamspace=teamspace,
        create=create,
        machine=machine,
        gpus=gpus,
        interruptible=interruptible,
        cloud_provider=cloud_provider,
        cloud_account=cloud_account,
        vm=False,
    )


def start_impl(
    name: Optional[str],
    teamspace: Optional[str],
    create: bool,
    machine: str,
    gpus: Optional[str],
    interruptible: bool,
    cloud_provider: Optional[str],
    cloud_account: Optional[str],
    vm: bool,
) -> None:
    menu = TeamspacesMenu()
    resolved_teamspace = menu(teamspace=teamspace)

    if cloud_provider is not None:
        cloud_provider = CloudProvider(cloud_provider)

    if not create:
        menu = StudiosMenu(resolved_teamspace, vm=vm)
        studio = menu(studio=name)
    else:
        create_cls = VM if vm else Studio
        studio = create_cls(
            name=name,
            teamspace=resolved_teamspace,
            create_ok=create,
            cloud_provider=cloud_provider,
            cloud_account=cloud_account,
        )

    machine = handle_machine_and_gpus_args(machine, gpus)

    save_studio_to_config(studio)

    Studio.show_progress = True
    studio.start(machine, interruptible=interruptible)
    click.echo(f"Studio {studio_name_link(studio)} started successfully")
