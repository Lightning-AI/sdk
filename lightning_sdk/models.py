import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from lightning_sdk.api import OrgApi, TeamspaceApi, UserApi
from lightning_sdk.api.utils import AccessibleResource, Experiment, raise_access_error_if_not_allowed
from lightning_sdk.lightning_cloud.openapi import V1ModelVersionArchive
from lightning_sdk.lightning_cloud.openapi.models import V1Membership, V1OwnerType
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.user import User
from lightning_sdk.utils.resolve import _get_authed_user, _resolve_teamspace

if TYPE_CHECKING:
    from lightning_sdk.teamspace import Teamspace


# TODO: Maybe just have a `Model` object?
@dataclass
class UploadedModelInfo:
    """Metadata returned after a successful model upload.

    Attributes:
        name: The model name as registered in the store.
        version: The assigned version tag (e.g. ``"v1"``).
        teamspace: Name of the teamspace the model was uploaded to.
        cloud_account: Cloud account ID where the model files are stored.
    """

    name: str
    version: str
    teamspace: str
    cloud_account: str


def _get_teamspace_and_path(
    ts: V1Membership, org_api: OrgApi, user_api: UserApi, authed_user: User
) -> Tuple[str, Dict[str, Any]]:
    """Return a ``(display_path, kwargs)`` tuple for a teamspace membership.

    Args:
        ts: The teamspace membership record.
        org_api: API client used to look up organisation names.
        user_api: API client used to look up user names.
        authed_user: The currently authenticated user.

    Returns:
        Tuple[str, Dict[str, Any]]: A display path such as ``"org/teamspace"`` and a dict
        of keyword arguments suitable for constructing a :class:`~lightning_sdk.Teamspace`.

    Raises:
        RuntimeError: If the membership has an unknown owner type.
    """
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
    """Return display paths for all teamspaces accessible to the authenticated user.

    Returns:
        List[str]: Paths in ``"owner/teamspace"`` format for every accessible teamspace.
    """
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


def _extend_model_name_with_teamspace(name: str) -> str:
    """Extend the model name with the teamspace if it can be determined from env. variables."""
    if "/" in name:
        return name
    # do some magic if you run studio
    teamspace = _resolve_teamspace(None, None, None)
    if not teamspace:
        raise ValueError(
            f"Model name must be in the format `organization/teamspace/model_name` but you provided '{name}'."
        )
    return f"{teamspace.owner.name}/{teamspace.name}/{name}"


def _parse_org_teamspace_model_version(name: str) -> Tuple[str, str, str, Optional[str]]:
    """Parse the name argument into its components."""
    try:
        org_name, teamspace_name, model_name = name.split("/")
    except ValueError as err:
        raise ValueError(
            f"Model name must be in the format `organization/teamspace/model_name` but you provided '{name}'."
        ) from err
    parts = model_name.split(":")
    if len(parts) == 1:
        return org_name, teamspace_name, parts[0], None
    if len(parts) == 2:
        return org_name, teamspace_name, parts[0], parts[1]
    # The rest of the validation for name and version happens in the backend
    raise ValueError(
        "Model version is expected to be in the format `organization/teamspace/model_name:version`"
        f" separated by a single colon, but got: {name}"
    )


def download_model(
    name: str,
    download_dir: Union[Path, str] = ".",
    progress_bar: bool = True,
) -> List[str]:
    """Download a model from the Lightning model store.

    Args:
        name: The fully-qualified model name in the format
            ``<ORGANIZATION>/<TEAMSPACE>/<MODEL-NAME>`` or
            ``<ORGANIZATION>/<TEAMSPACE>/<MODEL-NAME>:<VERSION>``.
        download_dir: Local directory to write the downloaded files into.
        progress_bar: Whether to display a download progress bar.

    Returns:
        List[str]: Local file paths of all downloaded model files.

    Raises:
        RuntimeError: If the model is not found or the download fails.
    """
    name = _extend_model_name_with_teamspace(name)
    teamspace_owner_name, teamspace_name, model_name, version = _parse_org_teamspace_model_version(name)

    api = TeamspaceApi()

    try:
        return api.download_model_files(
            name=model_name,
            version=version,
            download_dir=Path(download_dir).expanduser().resolve(),
            teamspace_name=teamspace_name,
            teamspace_owner_name=teamspace_owner_name,
            progress_bar=progress_bar,
        )
    except ApiException as e:
        if e.status == 404:
            raise RuntimeError(
                f"Model '{name}' not found. Either the model doesn't exist or you don't have access to it."
            ) from None
        raise RuntimeError(f"Error downloading model. Status code: {e.status}.") from None


def upload_model(
    name: str,
    path: Union[str, Path, List[Union[str, Path]]] = ".",
    cloud_account: Optional[str] = None,
    progress_bar: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
    experiment: Optional[Experiment] = None,
) -> UploadedModelInfo:
    """Upload a model to the Lightning model store.

    Args:
        name: Fully-qualified model name in the format
            ``<ORGANIZATION>/<TEAMSPACE>/<MODEL-NAME>`` or
            ``<ORGANIZATION>/<TEAMSPACE>/<MODEL-NAME>:<VERSION>``.
        path: Local file or directory to upload.  Defaults to the current directory.
        cloud_account: Cloud account to store the model files in.
            Falls back to the teamspace default when not provided.
        progress_bar: Whether to display an upload progress bar.
        metadata: Arbitrary key-value metadata attached to this model version.
        experiment: Optional experiment record to associate with this upload.

    Returns:
        UploadedModelInfo: Metadata about the newly uploaded model version.
    """
    name = _extend_model_name_with_teamspace(name)
    org_name, teamspace_name, model_name, version = _parse_org_teamspace_model_version(name)
    teamspace = _get_teamspace(name=teamspace_name, organization=org_name)
    raise_access_error_if_not_allowed(AccessibleResource.Models, teamspace.id)
    return teamspace.upload_model(
        path=path,
        name=model_name,
        version=version,
        cloud_account=cloud_account,
        progress_bar=progress_bar,
        metadata=metadata,
        experiment=experiment,
    )


def delete_model(
    name: str,
) -> None:
    """Delete a model or a version of model.

    Args:
        name: The name of the model you want to delete or with specified version it deltes only that version.
            This should have the format <ORGANIZATION-NAME>/<TEAMSPACE-NAME>/<MODEL-NAME> for full model deletion
            or <ORGANIZATION-NAME>/<TEAMSPACE-NAME>/<MODEL-NAME>:<VERSION> for version deletion.
    """
    name = _extend_model_name_with_teamspace(name)
    org_name, teamspace_name, model_name, version = _parse_org_teamspace_model_version(name)
    teamspace = _get_teamspace(name=teamspace_name, organization=org_name)
    raise_access_error_if_not_allowed(AccessibleResource.Models, teamspace.id)
    teamspace.delete_model(name=f"{model_name}:{version}" if version else model_name)


def list_model_versions(
    name: str,
) -> List[V1ModelVersionArchive]:
    """List all versions of a model.

    Args:
        name: Fully-qualified model name in the format
            ``<ORGANIZATION>/<TEAMSPACE>/<MODEL-NAME>``.

    Returns:
        List[V1ModelVersionArchive]: All registered version archives for the model.
    """
    name = _extend_model_name_with_teamspace(name)
    org_name, teamspace_name, model_name, _ = _parse_org_teamspace_model_version(name)
    teamspace = _get_teamspace(name=teamspace_name, organization=org_name)
    raise_access_error_if_not_allowed(AccessibleResource.Models, teamspace.id)
    return teamspace.list_model_versions(name=model_name)
