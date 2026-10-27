from dataclasses import dataclass
from typing import Optional, Tuple

from lightning_sdk.api.org_api import OrgApi
from lightning_sdk.api.teamspace_api import TeamspaceApi
from lightning_sdk.utils.config import Config, DefaultConfigKeys
from lightning_sdk.utils.filesystem import parse_lit_url
from lightning_sdk.utils.resolve import _resolve_org_name, _resolve_teamspace_name


@dataclass(frozen=True)
class TeamspaceRef:
    """The parts of a teamspace that reading its drive needs."""

    id: str
    name: str


def resolve_teamspace_ref(teamspace: Optional[str], owner: Optional[str]) -> TeamspaceRef:
    """Resolve a teamspace to the parts its drive operations need.

    Teamspaces are owned by organizations, so a teamspace resolves from two
    requests, the organization and the user's memberships, instead of building a
    full :class:`~lightning_sdk.Teamspace`. A missing name or owner is taken from
    the current teamspace's configuration, as :class:`~lightning_sdk.Teamspace` does.

    Raises:
        ValueError: If no teamspace is given or configured, the organization does
            not exist, or the user is not a member of a teamspace with that name in it.
    """
    teamspace = _resolve_teamspace_name(teamspace)
    owner = owner or _current_org_name()
    if not (teamspace and owner):
        raise ValueError("Could not resolve a teamspace. Use lit://<org>/<teamspace>/<path>.")

    org_id = OrgApi().find_org_id(owner)
    if not org_id:
        raise ValueError(f"Org {owner} does not exist")
    teamspace_id = TeamspaceApi().find_teamspace_id(name=teamspace, owner_id=org_id)
    if not teamspace_id:
        raise ValueError(f"Teamspace {teamspace} does not exist")
    return TeamspaceRef(id=teamspace_id, name=teamspace)


def _current_org_name() -> Optional[str]:
    """The organization of the current teamspace, from the environment or the config."""
    org = _resolve_org_name(None)
    if org:
        return org
    config = Config()
    if (config.get_value(DefaultConfigKeys.teamspace_owner_type) or "").lower() == "organization":
        return config.get_value(DefaultConfigKeys.teamspace_owner)
    return None


def resolve_lit_url_ref(url: str) -> Tuple[TeamspaceRef, str]:
    """Parse a ``lit://`` URL and resolve its teamspace with :func:`resolve_teamspace_ref`.

    Returns the teamspace and the drive path within it (``""`` for the teamspace
    root). The relative form (``lit:///<path>``) resolves to the current teamspace.
    """
    parsed = parse_lit_url(url)
    return resolve_teamspace_ref(parsed["teamspace"], parsed["owner"]), parsed["destination"] or ""
