from typing import List, Optional

import click

from lightning_sdk.cli.studio.ssh import ssh_impl


@click.command("ssh")
@click.option(
    "--name",
    help=(
        "The name of the VM to ssh into. "
        "If not provided, will try to infer from environment, "
        "use the default value from the config or prompt for interactive selection."
    ),
)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)", type=click.STRING)
@click.option(
    "--option",
    "-o",
    help="Additional options to pass to the SSH command. Can be specified multiple times.",
    multiple=True,
    type=click.STRING,
)
def ssh_vm(name: Optional[str] = None, teamspace: Optional[str] = None, option: Optional[List[str]] = None) -> None:
    """SSH into a VM.

    Example:
        lightning vm ssh --name my-vm
    """
    return ssh_impl(name=name, teamspace=teamspace, option=option, vm=False)
