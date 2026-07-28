from typing import Optional

import rich_click as click

from lightning_sdk.studio import Studio
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.utils.resolve import _resolve_teamspace


def join_teamspace_slug(owner: Optional[str], teamspace: Optional[str]) -> Optional[str]:
    if teamspace is None:
        return None
    return f"{owner}/{teamspace}" if owner else teamspace


def resolve_teamspace(
    teamspace: Optional[str] = None,
    org: Optional[str] = None,
    user: Optional[str] = None,
) -> Teamspace:
    if teamspace and "/" in teamspace and (org or user):
        raise click.UsageError("--teamspace already specifies its owner; remove --org/--user.")
    resolved = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
    if resolved is None:
        raise click.UsageError("Could not resolve a teamspace. Pass --teamspace OWNER/TEAMSPACE.")
    return resolved


def resolve_studio(name: Optional[str], teamspace: Teamspace) -> Studio:
    try:
        return Studio(name=name, teamspace=teamspace, create_ok=False)
    except ValueError as ex:
        detail = f" '{name}'" if name else ""
        raise click.UsageError(f"Could not resolve studio{detail}. Pass --name STUDIO.") from ex
