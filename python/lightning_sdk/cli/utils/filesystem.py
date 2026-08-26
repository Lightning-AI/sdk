from typing import Optional, Tuple

from lightning_sdk.cli.utils.resource_resolution import join_teamspace_slug
from lightning_sdk.cli.utils.resource_resolution import resolve_teamspace as resolve_cli_teamspace
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.utils.filesystem import parse_lit_url


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
