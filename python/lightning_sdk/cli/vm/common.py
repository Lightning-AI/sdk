"""Shared helpers for VM CLI commands."""

import json
from typing import Iterable, Optional

import rich_click as click

from lightning_sdk.api.vm_api import VMApi
from lightning_sdk.cli.utils.teamspace_option import resolve_teamspace
from lightning_sdk.lightning_cloud.openapi import V1Instance
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.machine import Machine
from lightning_sdk.models import _list_teamspaces
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User

MACHINE_VALUES = tuple(
    [machine.name for machine in Machine.__dict__.values() if isinstance(machine, Machine) and machine._include_in_cli]
)

_SSH_KEY_HINT = " Generate one with 'lightning ssh generate'."


def iter_teamspaces(teamspace: Optional[str], all_teamspaces: bool) -> Iterable[Teamspace]:
    if not all_teamspaces or teamspace:
        yield resolve_teamspace(teamspace)
        return

    for teamspace_slug in _list_teamspaces():
        yield resolve_teamspace(teamspace_slug)


def org_id_for(teamspace: Teamspace) -> str:
    owner = teamspace.owner
    if isinstance(owner, User):
        raise click.ClickException(
            f"VMs require a teamspace owned by an organization; '{teamspace.name}' is owned by a user."
        )
    return owner.id


def resolve_vm(api: VMApi, teamspace: Teamspace, name_or_id: str) -> V1Instance:
    org_id = org_id_for(teamspace)
    try:
        vm = api.get_vm_by_name(name_or_id, teamspace.id)
    except ValueError as ex:
        raise click.ClickException(str(ex)) from ex
    if vm is None:
        try:
            vm = api.get_vm(name_or_id, org_id)
        except ApiException as ex:
            raise friendly_error(ex) from ex
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
