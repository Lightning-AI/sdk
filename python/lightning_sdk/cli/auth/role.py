"""Describe a role's permissions."""

import json
from typing import Optional

import rich_click as click
from rich.table import Table

from lightning_sdk.api.auth_api import AuthApi
from lightning_sdk.cli.auth._labels import (
    action_label,
    condition_label,
    effect_label,
    is_visible_action,
    is_visible_resource,
    resource_label,
)
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_teamspace
from lightning_sdk.cli.utils.richt_print import rich_to_str

_TEAMSPACE_HELP = "Teamspace the role belongs to, as 'owner/teamspace'. Falls back to your default teamspace."


@click.command("role", cls=LightningCommand)
@click.argument("role_id")
@click.option("--teamspace", help=_TEAMSPACE_HELP)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output the role as JSON.")
def role(role_id: str, teamspace: Optional[str] = None, as_json: bool = False) -> None:
    """Describe what a role is allowed to do.

    ROLE_ID is the id of the role; run `lightning auth roles` to find it.
    """
    resolved = resolve_teamspace(teamspace)
    role_obj = AuthApi().get_role(resolved.id, role_id)

    # Explode each rule into one row per resource, using user-facing labels.
    # Unspecified sentinel actions/resources carry no meaning, so they are dropped;
    # a rule left with no visible actions or resources is skipped entirely.
    entries = []
    for rule in role_obj.rules or []:
        actions = [action_label(a) for a in (rule.actions or []) if is_visible_action(a)]
        if not actions:
            continue
        actions_str = ", ".join(actions)
        effect = effect_label(rule.effect)
        condition = condition_label(rule.condition)
        for resource in rule.resources or []:
            if not is_visible_resource(resource):
                continue
            entries.append(
                {
                    "resource": resource_label(resource),
                    "actions": actions_str,
                    "effect": effect,
                    "condition": condition,
                }
            )
    entries.sort(key=lambda entry: (entry["resource"], entry["effect"]))

    if as_json:
        payload = {
            "id": role_obj.id,
            "name": role_obj.name,
            "description": role_obj.description or None,
            "permissions": entries,
        }
        click.echo(json.dumps(payload, indent=2))
        return

    heading = role_obj.name
    if role_obj.description:
        heading += f" — {role_obj.description}"
    click.echo(heading)

    table = Table()
    table.add_column("Resource")
    table.add_column("Actions")
    table.add_column("Effect")
    table.add_column("Condition")
    for entry in entries:
        table.add_row(entry["resource"], entry["actions"], entry["effect"], entry["condition"] or "")

    click.echo(rich_to_str(table), color=True)
