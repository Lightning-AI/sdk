from typing import Optional, TypedDict

from lightning_sdk.cli.utils.owner_selection import OwnerMenu
from lightning_sdk.cli.utils.studio_selection import StudiosMenu
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.studio import Studio


class StudioPathResult(TypedDict):
    owner: Optional[str]
    teamspace: Optional[str]
    studio: Optional[str]
    destination: Optional[str]


def parse_studio_path(studio_path: str) -> StudioPathResult:
    path_string = studio_path.removeprefix("lit://")
    if not path_string:
        raise ValueError("Studio path cannot be empty after prefix")

    result: StudioPathResult = {"owner": None, "teamspace": None, "studio": None, "destination": None}

    if "/studios/" in path_string:
        prefix_part, suffix_part = path_string.split("/studios/", 1)

        # org and teamspace
        if prefix_part:
            org_ts_components = prefix_part.split("/")
            if len(org_ts_components) == 2:
                result["owner"], result["teamspace"] = org_ts_components
            elif len(org_ts_components) == 1:
                result["teamspace"] = org_ts_components[0]
            else:
                raise ValueError(f"Invalid format: '{prefix_part}'")

        # studio and destination
        path_parts = suffix_part.split("/")

    else:
        # studio and destination
        path_parts = path_string.split("/")

    if not path_parts or len(path_parts) < 2:
        raise ValueError("Invalid: Missing studio name.")

    result["studio"] = path_parts[0]
    result["destination"] = "/".join(path_parts[1:])

    return result


def resolve_studio(studio_name: Optional[str], teamspace: Optional[str], owner: Optional[str]) -> Studio:
    owner_menu = OwnerMenu()
    resolved_owner = owner_menu(owner=owner)

    teamspace_menu = TeamspacesMenu(resolved_owner)
    resolved_teamspace = teamspace_menu(teamspace=teamspace)

    studio_menu = StudiosMenu(resolved_teamspace)
    return studio_menu(studio=studio_name)
