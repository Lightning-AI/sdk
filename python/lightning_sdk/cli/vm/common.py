"""Shared helpers for VM CLI commands."""

import json
from typing import Iterable, Optional

import rich_click as click

from lightning_sdk.api.vm_api import VMApi
from lightning_sdk.cli.utils.save_to_config import save_teamspace_to_config
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.lightning_cloud.openapi import V1Instance
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.machine import Machine
from lightning_sdk.organization import Organization
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User
from lightning_sdk.utils.resolve import _get_authed_user

MACHINE_VALUES = tuple(
    [machine.name for machine in Machine.__dict__.values() if isinstance(machine, Machine) and machine._include_in_cli]
)

_SSH_KEY_HINT = " Generate one with 'lightning ssh generate' or add it under Settings → Keys."


def resolve_teamspace(teamspace: Optional[str]) -> Teamspace:
    resolved_teamspace = TeamspacesMenu()(teamspace=teamspace)
    save_teamspace_to_config(resolved_teamspace, overwrite=False)
    return resolved_teamspace


def iter_teamspaces(teamspace: Optional[str], all_teamspaces: bool) -> Iterable[Teamspace]:
    if not all_teamspaces or teamspace:
        yield resolve_teamspace(teamspace)
        return

    user = _get_authed_user()
    menu = TeamspacesMenu()
    possible_teamspaces = menu._get_possible_teamspaces(user)
    for teamspace_name in possible_teamspaces.values():
        owner = menu._owner
        yield Teamspace(
            teamspace_name,
            org=owner if isinstance(owner, Organization) else None,
            user=owner if isinstance(owner, User) else None,
        )


def org_id_for(teamspace: Teamspace) -> str:
    owner = teamspace.owner
    if isinstance(owner, User):
        raise click.ClickException(
            f"VMs require a teamspace owned by an organization; '{teamspace.name}' is owned by a user."
        )
    return owner.id


def resolve_vm(api: VMApi, teamspace: Teamspace, name_or_id: str) -> V1Instance:
    org_id = org_id_for(teamspace)
    vm = api.get_vm_by_name(name_or_id, teamspace.id, org_id)
    if vm is None:
        vm = api.get_vm(name_or_id, org_id)
    if vm is None:
        raise click.ClickException(
            f"VM {name_or_id!r} was not found in teamspace '{teamspace.owner.name}/{teamspace.name}'."
        )
    return vm


def server_message(ex: ApiException) -> str:
    body = getattr(ex, "body", None)
    if body:
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict) and parsed.get("message"):
                return str(parsed["message"])
        except (TypeError, ValueError):
            pass
    return str(ex.reason or ex)


def friendly_error(ex: ApiException) -> click.ClickException:
    message = server_message(ex)
    if "add an SSH key" in message:
        message += _SSH_KEY_HINT
    return click.ClickException(message)
