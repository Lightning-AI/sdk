from typing import Tuple

from lightning_sdk.api import OrgApi, UserApi
from lightning_sdk.cli.exceptions import StudioCliError
from lightning_sdk.teamspace import Teamspace
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


def _get_teamspace(name: str, organization: str) -> Teamspace:
    """Get a Teamspace object from the SDK."""
    org_api = OrgApi()
    user = _get_authed_user()
    teamspaces = {}
    for ts in UserApi()._get_all_teamspace_memberships(""):
        if ts.owner_type == "organization":
            org = org_api._get_org_by_id(ts.owner_id)
            teamspaces[f"{org.name}/{ts.name}"] = {"name": ts.name, "org": org.name}
        elif ts.owner_type == "user":  # todo: check also the name
            teamspaces[f"{user.name}/{ts.name}"] = {"name": ts.name, "user": user}
        else:
            raise StudioCliError(f"Unknown organization type {ts.owner_type}")

    requested_teamspace = f"{organization}/{name}".lower()
    if requested_teamspace not in teamspaces:
        options = "\n\t".join(teamspaces.keys())
        raise StudioCliError(f"Teamspace `{requested_teamspace}` not found. Available teamspaces: \n\t{options}")
    return Teamspace(**teamspaces[requested_teamspace])
