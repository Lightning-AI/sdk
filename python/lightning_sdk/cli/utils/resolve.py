from typing import Optional

from lightning_sdk.teamspace import Teamspace
from lightning_sdk.utils.resolve import _resolve_teamspace


def resolve_teamspace_owner_name_format(teamspace_name: Optional[str]) -> Optional[Teamspace]:
    teamspace_resolved = None
    if teamspace_name is None:
        return _resolve_teamspace(None, None, None)

    splits = teamspace_name.split("/")
    if len(splits) == 1:
        try:
            teamspace_resolved = _resolve_teamspace(teamspace_name, None, None)
        except Exception:
            teamspace_resolved = None

    elif len(splits) == 2:
        try:
            try:
                teamspace_resolved = _resolve_teamspace(splits[1], splits[0], None)
            except Exception:
                teamspace_resolved = _resolve_teamspace(splits[1], None, splits[0])
        except Exception:
            teamspace_resolved = None

    return teamspace_resolved
