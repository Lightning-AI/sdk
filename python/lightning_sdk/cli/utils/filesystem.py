import os
from typing import Any, Optional, TypedDict

from lightning_sdk.cli.utils.owner_selection import OwnerMenu
from lightning_sdk.cli.utils.studio_selection import StudiosMenu
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.studio import Studio
from lightning_sdk.teamspace import Teamspace


class PathResult(TypedDict):
    owner: Optional[str]
    teamspace: Optional[str]
    studio: Optional[str]
    destination: Optional[str]


def path_join(*args: Any) -> str:
    return os.path.join(*args).replace("\\", "/")


def parse_studio_path(studio_path: str) -> PathResult:
    prefix = "lit://"
    path_string = studio_path[len(prefix) :] if studio_path.startswith(prefix) else studio_path
    if not path_string:
        raise ValueError("Studio path cannot be empty after prefix")

    result: PathResult = {"owner": None, "teamspace": None, "studio": None, "destination": None}

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

    if not path_parts:
        raise ValueError("Invalid: Missing studio name.")

    if len(path_parts) == 1:
        raise ValueError(
            "Invalid: Invalid studio path. To refer to the studio root, add a trailing '/' (e.g., 'lit://<owner>/<my-teamspace>/studios/<my-studio>/')"
        )

    result["studio"] = path_parts[0]
    result["destination"] = "/".join(path_parts[1:])

    return result


def parse_teamspace_uploads_path(teamspace_path: str) -> PathResult:
    prefix = "lit://"
    path_string = teamspace_path[len(prefix) :] if teamspace_path.startswith(prefix) else teamspace_path
    if not path_string:
        raise ValueError("Teamspace path cannot be empty after prefix")

    result: PathResult = {"owner": None, "teamspace": None, "studio": None, "destination": None}

    if "/uploads/" in path_string:
        prefix_part, suffix_part = path_string.split("/uploads/", 1)

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
        raise ValueError("Invalid teamspace uploads path: missing '/uploads/' segment")

    if not path_parts:
        raise ValueError("Invalid: Missing teamspace name.")

    result["destination"] = suffix_part

    return result


def resolve_teamspace(teamspace: Optional[str], owner: Optional[str]) -> Teamspace:
    owner_menu = OwnerMenu()
    resolved_owner = owner_menu(owner=owner)

    teamspace_menu = TeamspacesMenu(resolved_owner)
    return teamspace_menu(teamspace=teamspace)


def resolve_studio(studio_name: Optional[str], teamspace: Optional[str], owner: Optional[str]) -> Studio:
    resolved_teamspace = resolve_teamspace(teamspace, owner)
    studio_menu = StudiosMenu(resolved_teamspace)
    return studio_menu(studio=studio_name)
