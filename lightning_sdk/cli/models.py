import os
from typing import Any, Dict, List, Tuple

from lightning_sdk.api import OrgApi, UserApi
from lightning_sdk.cli.exceptions import StudioCliError
from lightning_sdk.lightning_cloud.openapi.models import V1Membership, V1OwnerType
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User
from lightning_sdk.utils.resolve import _get_authed_user


def _parse_model_name(name: str) -> Tuple[str, str, str]:
    """Parse the name argument into its components."""
    try:
        org_name, teamspace_name, model_name = name.split("/")
    except ValueError as err:
        raise StudioCliError(
            f"Model name must be in the format 'organization/teamspace/model' but you provided '{name}'."
        ) from err
    return org_name, teamspace_name, model_name


def _get_teamspace_and_path(
    ts: V1Membership, org_api: OrgApi, user_api: UserApi, authed_user: User
) -> Tuple[str, Dict[str, Any]]:
    if ts.owner_type == V1OwnerType.ORGANIZATION:
        org = org_api._get_org_by_id(ts.owner_id)
        return f"{org.name}/{ts.name}", {"name": ts.name, "org": org.name}

    if ts.owner_type == V1OwnerType.USER and ts.owner_id != authed_user.id:
        user = user_api._get_user_by_id(ts.owner_id)  # todo: check also the name
        return f"{user.username}/{ts.name}", {"name": ts.name, "user": User(name=user.username)}

    if ts.owner_type == V1OwnerType.USER:
        return f"{authed_user.name}/{ts.name}", {"name": ts.name, "user": authed_user}

    raise StudioCliError(f"Unknown organization type {ts.owner_type}")


def _list_teamspaces() -> List[str]:
    org_api = OrgApi()
    user_api = UserApi()
    authed_user = _get_authed_user()

    return [
        _get_teamspace_and_path(ts, org_api, user_api, authed_user)[0]
        for ts in user_api._get_all_teamspace_memberships("")
    ]


def _get_teamspace(name: str, organization: str) -> Teamspace:
    """Get a Teamspace object from the SDK."""
    org_api = OrgApi()
    user_api = UserApi()
    authed_user = _get_authed_user()

    requested_teamspace = f"{organization}/{name}".lower()

    for ts in user_api._get_all_teamspace_memberships(""):
        if ts.name != name:
            continue

        teamspace_path, teamspace = _get_teamspace_and_path(ts, org_api, user_api, authed_user)
        if requested_teamspace == teamspace_path:
            return Teamspace(**teamspace)

    options = f"{os.linesep}\t".join(_list_teamspaces())
    raise StudioCliError(f"Teamspace `{requested_teamspace}` not found. Available teamspaces: {os.linesep}\t{options}")
