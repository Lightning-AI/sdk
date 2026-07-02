"""Studio start command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.utils.handle_machine_and_gpus_args import handle_machine_and_gpus_args
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.richt_print import studio_name_link
from lightning_sdk.cli.utils.save_to_config import save_studio_to_config
from lightning_sdk.cli.utils.studio_selection import StudiosMenu
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.machine import Machine
from lightning_sdk.studio import Studio

click.rich_click.OPTION_GROUPS = {
    "lightning studio start": [
        {"name": "STUDIO", "options": ["--name", "--teamspace", "--create"]},
        {"name": "COMPUTE", "options": ["--machine", "--gpus", "--interruptible", "--cloud"]},
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
def start_studio(
    name: Optional[str] = None,
    teamspace: Optional[str] = None,
    create: bool = False,
    machine: str = "CPU",
    gpus: Optional[str] = None,
    interruptible: bool = False,
    cloud: Optional[str] = None,
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
    )


def start_impl(
    name: Optional[str],
    teamspace: Optional[str],
    create: bool,
    machine: str,
    gpus: Optional[str],
    interruptible: bool,
    cloud: Optional[str] = None,
) -> None:
    menu = TeamspacesMenu()
    resolved_teamspace = menu(teamspace=teamspace)

    if not create:
        menu = StudiosMenu(resolved_teamspace)
        studio = menu(studio=name)
    else:
        studio = Studio(
            name=name,
            teamspace=resolved_teamspace,
            create_ok=create,
            cloud=cloud,
        )

    machine = handle_machine_and_gpus_args(machine, gpus)

    save_studio_to_config(studio)

    Studio.show_progress = True
    studio.start(machine, interruptible=interruptible)
    click.echo(f"Studio {studio_name_link(studio)} started successfully")
