import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from lightning_sdk.api import OrgApi, TeamspaceApi, UserApi
from lightning_sdk.lightning_cloud.openapi.models import V1Membership, V1OwnerType
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.user import User
from lightning_sdk.utils.resolve import _get_authed_user

if TYPE_CHECKING:
    from lightning_sdk.teamspace import Teamspace


# TODO: Maybe just have a `Model` object?
@dataclass
class UploadedModelInfo:
    name: str
    version: str
    teamspace: str
    cloud_account: str


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

    raise RuntimeError(f"Unknown organization type {ts.owner_type}")


def _list_teamspaces() -> List[str]:
    org_api = OrgApi()
    user_api = UserApi()
    authed_user = _get_authed_user()

    return [
        _get_teamspace_and_path(ts, org_api, user_api, authed_user)[0]
        for ts in user_api._get_all_teamspace_memberships("")
    ]


def _get_teamspace(name: str, organization: str) -> "Teamspace":
    """Get a Teamspace object from the SDK."""
    from lightning_sdk.teamspace import Teamspace

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
    raise RuntimeError(f"Teamspace `{requested_teamspace}` not found. Available teamspaces: {os.linesep}\t{options}")


def _parse_model_name_and_version(name: str) -> Tuple[str, str, str, str]:
    """Parse the name argument into its components."""
    try:
        org_name, teamspace_name, model_name = name.split("/")
        parts = model_name.split(":")
        if len(parts) == 1:
            return org_name, teamspace_name, parts[0], "latest"
        if len(parts) == 2:
            return org_name, teamspace_name, parts[0], parts[1]
        # The rest of the validation for name and version happens in the backend
        raise ValueError(
            "Model version is expected to be in the format `entity/modelname:version` separated by a"
            f" single colon, but got: {name}"
        )
    except ValueError as err:
        raise ValueError(
            f"Model name must be in the format 'organization/teamspace/model' but you provided '{name}'."
        ) from err


def download_model(
    name: str,
    download_dir: Union[Path, str] = ".",
    progress_bar: bool = True,
) -> List[str]:
    """Download a Model.

    Args:
        name: The name of the Model you want to download.
        This should have the format <ORGANIZATION-NAME>/<TEAMSPACE-NAME>/<MODEL-NAME>.
        download_dir: The directory where the Model should be downloaded.
        progress_bar: Whether to show a progress bar when downloading.
    """
    teamspace_owner_name, teamspace_name, model_name, version = _parse_model_name_and_version(name)

    download_dir = Path(download_dir)

    api = TeamspaceApi()

    try:
        return api.download_model_files(
            name=model_name,
            version=version,
            download_dir=download_dir,
            teamspace_name=teamspace_name,
            teamspace_owner_name=teamspace_owner_name,
            progress_bar=progress_bar,
        )
    except ApiException as e:
        # if we get an error, check if the teamspace actually exists (and print the list)
        # TODO: ideally this would match a specific error about teamspace not being found
        _ = _get_teamspace(name=teamspace_name, organization=teamspace_owner_name)
        raise e


def upload_model(
    name: str,
    path: Union[Path, str] = ".",
    cloud_account: Optional[str] = None,
    progress_bar: bool = True,
) -> UploadedModelInfo:
    """Upload a Model.

    Args:
        name: The name of the Model you want to upload.
            This should have the format <ORGANIZATION-NAME>/<TEAMSPACE-NAME>/<MODEL-NAME>.
        path: The path to the file or directory you want to upload. Defaults to the current directory.
        cloud_account: The name of the cloud account to store the Model in.
            If not provided, the default cloud account for the Teamspace will be used.
        progress_bar: Whether to show a progress bar for the upload.
    """
    org_name, teamspace_name, model_name, _ = _parse_model_name_and_version(name)
    teamspace = _get_teamspace(name=teamspace_name, organization=org_name)
    return teamspace.upload_model(
        path=path,
        name=model_name,
        cloud_account=cloud_account,
        progress_bar=progress_bar,
    )
