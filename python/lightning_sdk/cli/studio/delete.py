"""Studio delete command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_studio, resolve_teamspace


@click.command("delete", cls=LightningCommand)
@click.option(
    "--name",
    help="Studio to use. Falls back to the current Studio or configured default.",
)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
@click.option("--yes", "-y", is_flag=True, default=False, help="Confirm deletion without prompting.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def delete_studio(
    name: Optional[str] = None,
    teamspace: Optional[str] = None,
    yes: bool = False,
    as_json: bool = False,
) -> None:
    """Delete a Studio.

    Example:
      lightning studio delete --name my-studio

    """
    return delete_impl(name=name, teamspace=teamspace, yes=yes, as_json=as_json)


def delete_impl(name: Optional[str], teamspace: Optional[str], yes: bool, as_json: bool = False) -> None:
    if not yes:
        raise click.UsageError("Deleting a studio requires --yes.")

    resolved_teamspace = resolve_teamspace(teamspace)
    studio = resolve_studio(name, resolved_teamspace)

    studio.delete()

    if as_json:
        echo_json({"name": studio.name, "deleted": True})
        return

    click.echo(f"{studio._cls_name} '{studio.name}' deleted successfully")
