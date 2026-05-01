from typing import Optional

import click

from lightning_sdk.cli.studio.delete import delete_impl


@click.command("delete")
@click.option(
    "--name",
    help=(
        "The name of the VM to delete. "
        "If not provided, will try to infer from environment, "
        "use the default value from the config or prompt for interactive selection."
    ),
)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
def delete_vm(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Delete a VM.

    Example:
      lightning vm delete --name my-vm

    """
    return delete_impl(name=name, teamspace=teamspace, vm=True)
