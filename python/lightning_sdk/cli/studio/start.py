"""Studio start command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.utils.cloud_selection import warn_deprecated_cloud_options
from lightning_sdk.cli.utils.handle_machine_and_gpus_args import handle_machine_and_gpus_args
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.richt_print import studio_name_link
from lightning_sdk.cli.utils.save_to_config import save_studio_to_config
from lightning_sdk.cli.utils.studio_selection import StudiosMenu
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.machine import CloudProvider, Machine
from lightning_sdk.studio import VM, Studio

click.rich_click.OPTION_GROUPS = {
    "lightning studio start": [
        {"name": "STUDIO", "options": ["--name", "--teamspace", "--create"]},
        {"name": "COMPUTE", "options": ["--machine", "--gpus", "--interruptible", "--cloud"]},
        {"name": "DEPRECATED", "options": ["--cloud-provider", "--cloud-account"]},
    ],
}


@click.command("start", cls=LightningCommand)
@click.option(
    "--name",
    help="Studio to start. Falls back to config/env, else prompts.",
)
@click.option(
    "--teamspace",
    metavar="OWNER/NAME",
    help="Override the default teamspace.",
)
@click.option("--create", is_flag=True, help="Create the Studio if it doesn't exist.")
@click.option(
    "--machine",
    metavar="TYPE",
    help=(
        "Machine type to start on. Default: [bold #6FB3E8]CPU_4[/bold #6FB3E8].\n\n"
        "[#6FB3E8]CPU[/#6FB3E8] · [#6FB3E8]T4[/#6FB3E8] · [#6FB3E8]L4[/#6FB3E8] · "
        "[#6FB3E8]L40S[/#6FB3E8] · [#6FB3E8]RTXP_6000[/#6FB3E8] · [#6FB3E8]A100[/#6FB3E8] · "
        "[#6FB3E8]H100[/#6FB3E8] · [#6FB3E8]H200[/#6FB3E8] · [#6FB3E8]B200[/#6FB3E8]  x1-8\n"
        "· full list: [bold #a78bfa]lightning machine list[/bold #a78bfa]"
    ),
    type=click.Choice(m.name for m in Machine.__dict__.values() if isinstance(m, Machine) and m._include_in_cli),
)
@click.option(
    "--gpus",
    metavar="TYPE:COUNT",
    help="GPUs to attach, e.g. [bold #6FB3E8]L4:4[/bold #6FB3E8].",
    type=click.STRING,
)
@click.option("--interruptible", is_flag=True, help="Use a cheaper interruptible (spot) instance.")
@click.option(
    "--cloud",
    help="Cloud provider or account. Default: teamspace. (with --create)",
)
@click.option(
    "--cloud-provider",
    metavar="",
    help="Deprecated — use [bold #a78bfa]--cloud[/bold #a78bfa].",
    type=click.Choice(m.name for m in list(CloudProvider)),
)
@click.option(
    "--cloud-account",
    metavar="",
    help="Deprecated — use [bold #a78bfa]--cloud[/bold #a78bfa].",
    type=click.STRING,
)
def start_studio(
    name: Optional[str] = None,
    teamspace: Optional[str] = None,
    create: bool = False,
    machine: str = "CPU",
    gpus: Optional[str] = None,
    interruptible: bool = False,
    cloud: Optional[str] = None,
    cloud_provider: Optional[str] = None,
    cloud_account: Optional[str] = None,
) -> None:
    """Start a Studio — a persistent GPU cloud workspace.

    Example:
        lightning studio start --name my-studio --machine A100 --create

    """
    return start_impl(
        name=name,
        teamspace=teamspace,
        create=create,
        machine=machine,
        gpus=gpus,
        interruptible=interruptible,
        cloud=cloud,
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
    cloud: Optional[str] = None,
    cloud_provider: Optional[str] = None,
    cloud_account: Optional[str] = None,
    vm: bool = False,
) -> None:
    menu = TeamspacesMenu()
    resolved_teamspace = menu(teamspace=teamspace)

    if cloud_provider is not None:
        cloud_provider = CloudProvider(cloud_provider)
    warn_deprecated_cloud_options(cloud_account=cloud_account, cloud_provider=cloud_provider)

    if not create:
        menu = StudiosMenu(resolved_teamspace, vm=vm)
        studio = menu(studio=name)
    else:
        create_cls = VM if vm else Studio
        studio = create_cls(
            name=name,
            teamspace=resolved_teamspace,
            create_ok=create,
            cloud=cloud,
            cloud_provider=cloud_provider,
            cloud_account=cloud_account,
        )

    machine = handle_machine_and_gpus_args(machine, gpus)

    save_studio_to_config(studio)

    Studio.show_progress = True
    studio.start(machine, interruptible=interruptible)
    click.echo(f"Studio {studio_name_link(studio)} started successfully")
