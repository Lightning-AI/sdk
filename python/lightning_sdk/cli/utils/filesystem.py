from dataclasses import dataclass
from typing import Optional, Tuple

from lightning_sdk.api.org_api import OrgApi
from lightning_sdk.api.teamspace_api import TeamspaceApi
from lightning_sdk.cli.utils.resource_resolution import join_teamspace_slug
from lightning_sdk.cli.utils.resource_resolution import resolve_teamspace as resolve_cli_teamspace
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.utils.filesystem import parse_lit_url


@dataclass(frozen=True)
class TeamspaceRef:
    """The parts of a teamspace that reading its drive needs."""

    id: str
    name: str


def resolve_teamspace(teamspace: Optional[str], owner: Optional[str]) -> Teamspace:
    return resolve_cli_teamspace(join_teamspace_slug(owner, teamspace))


def resolve_lit_url(url: str) -> Tuple[Teamspace, str]:
    """Parse a ``lit://`` URL and resolve its teamspace in one step.

    Returns the resolved :class:`Teamspace` and the drive path within it
    (``""`` for the teamspace root). The relative form (``lit:///<path>``)
    resolves to the current teamspace.
    """
    parsed = parse_lit_url(url)
    return resolve_teamspace(parsed["teamspace"], parsed["owner"]), parsed["destination"] or ""


def resolve_lit_url_ref(url: str) -> Tuple[TeamspaceRef, str]:
    """Like :func:`resolve_lit_url`, for operations that need only the teamspace's ID.

    A teamspace owned by an organization resolves from two requests, the
    organization and the user's memberships, instead of building a full
    :class:`Teamspace`. The relative form, and a teamspace owned by a user,
    resolve through :func:`resolve_lit_url`.
    """
    parsed = parse_lit_url(url)
    owner, name = parsed["owner"], parsed["teamspace"]
    destination = parsed["destination"] or ""
    if owner and name:
        org_id = OrgApi().find_org_id(owner)
        teamspace_id = TeamspaceApi().find_teamspace_id(name=name, owner_id=org_id) if org_id else None
        if teamspace_id:
            return TeamspaceRef(id=teamspace_id, name=name), destination

    teamspace = resolve_teamspace(name, owner)
    return TeamspaceRef(id=teamspace.id, name=teamspace.name), destination
