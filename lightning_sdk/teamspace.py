from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Union

from lightning_sdk.agents import Agent
from lightning_sdk.api import TeamspaceApi
from lightning_sdk.organization import Organization
from lightning_sdk.owner import Owner
from lightning_sdk.user import User
from lightning_sdk.utils import _get_organizations_for_authed_user, _resolve_org, _resolve_teamspace_name, _resolve_user

if TYPE_CHECKING:
    from lightning_sdk.studio import Studio


class Teamspace:
    """A teamspace is a collection of Studios, Clusters, Members and an associated Budget.

    Args:
        name: the name of the teamspace
        org: the owning organization
        user: the owning user

    Note:
        Either user or organization should be specified.

    Note:
        Arguments will be automatically inferred from environment variables if possible,
        unless explicitly specified

    """

    def __init__(
        self,
        name: Optional[str] = None,
        org: Optional[Union[str, Organization]] = None,
        user: Optional[Union[str, User]] = None,
    ) -> None:
        self._teamspace_api = TeamspaceApi()

        name = _resolve_teamspace_name(name)

        if name is None:
            raise ValueError("Teamspace name wasn't provided and could not be inferred from environment")

        if user is not None and org is not None:
            raise ValueError("User and org are mutually exclusive. Please only specify the one who owns the teamspace.")

        if user is not None:
            self._user = _resolve_user(user)
            # don't parse org if user was explicitly provided
            self._org = None
        else:
            self._user = _resolve_user(user)
            self._org = _resolve_org(org)

        self._owner: Owner
        if self._user is None and self._org is None:
            raise RuntimeError(
                "Neither user or org are specified, but one of them has to be the owner of the Teamspace"
            )
        elif self._org is not None:
            self._owner = self._org

        else:
            self._owner = self._user

        try:
            self._teamspace = self._teamspace_api.get_teamspace(name=name, owner_id=self.owner.id)
        except ValueError as e:
            raise _resolve_valueerror_message(e, self.owner, name) from e

    @property
    def name(self) -> str:
        """The teamspace's name."""
        return self._teamspace.name

    @property
    def id(self) -> str:
        """The teamspace's ID."""
        return self._teamspace.id

    @property
    def owner(self) -> Owner:
        """The teamspace's owner."""
        return self._owner

    @property
    def studios(self) -> List["Studio"]:
        """All studios within that teamspace."""
        from lightning_sdk.studio import Studio

        studios = []
        clusters = self._teamspace_api.list_clusters(teamspace_id=self.id)
        for cl in clusters:
            _studios = self._teamspace_api.list_studios(teamspace_id=self.id, cluster_id=cl.cluster_id)
            for s in _studios:
                studios.append(Studio(name=s.name, teamspace=self, cluster=cl.cluster_name, create_ok=False))

        return studios

    @property
    def clusters(self) -> List[str]:
        """All clusters associated with that teamspace."""
        clusters = self._teamspace_api.list_clusters(teamspace_id=self.id)
        return [cl.cluster_name for cl in clusters]

    def __eq__(self, other: "Teamspace") -> bool:
        """Checks whether the provided other object is equal to this one."""
        return (
            type(self) is type(other) and self.name == other.name and self.id == other.id and self.owner == other.owner
        )

    def __repr__(self) -> str:
        """Returns reader friendly representation."""
        return f"Teamspace(name={self.name}, owner={self.owner!r})"

    def __str__(self) -> str:
        """Returns reader friendly representation."""
        return repr(self)

    def create_agent(
        self,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        org_id: Optional[str] = "",
        prompt_template: Optional[str] = "",
        description: Optional[str] = "",
        prompt_suggestions: Optional[List[str]] = None,
        file_uploads_enabled: Optional[bool] = None,
    ) -> "Agent":
        agent = self._teamspace_api.create_agent(
            teamspace_id=self.id,
            name=name,
            api_key=api_key,
            base_url=base_url,
            model=model,
            org_id=org_id,
            prompt_template=prompt_template,
            description=description,
            prompt_suggestions=prompt_suggestions,
            file_uploads_enabled=file_uploads_enabled,
        )
        return Agent(agent.id)

    def upload_model(
        self,
        path: str,
        name: str,
        private: bool = True,
        progress_bar: bool = True,
        cluster_id: Optional[str] = None,
    ) -> None:
        """Upload a local checkpoint file to the model store.

        Args:
            path: Path to the model file to upload.
            name: Name tag of the model to upload. Must be in the format 'entity/modelname' where
                entity is either your user name or the name of an organization you are part of.
            private: Whether the model is accessible publicly or only by you (or in case of
                an organization only by the members of this organization).
            progress_bar: Whether to show a progress bar for the upload.
            cluster_id: The name of the cluster to use. Only required if it can't be determined
                automatically.

        """
        path = Path(path)
        if path.is_dir():
            raise NotImplementedError("Uploading directories is not yet supported.")
        if not path.exists():
            raise FileNotFoundError(str(path))

        cluster_id = self._teamspace_api._try_get_cluster_id(self.id) if cluster_id is None else cluster_id
        upload_dir, cluster_id = self._teamspace_api.request_artifact_upload(
            name=name,
            metadata={"filenames": path.name},
            private=private,
            teamspace_id=self.id,
            version=None,  # TODO: Support version as input
            cluster_id=cluster_id,
        )
        self._teamspace_api.upload_artifact_file(
            local_file_path=path,
            remote_dir=upload_dir,
            cluster_id=cluster_id,
            teamspace_id=self.id,
            progress_bar=progress_bar,
        )

    def download_model(
        self,
        name: str,
        download_dir: Optional[str] = None,
    ) -> str:
        """Download a checkpoint from the model store.

        Args:
            name: Name tag of the model to download. Must be in the format 'entity/modelname' where
                entity is either your user name or the name of an organization you are part of.
            download_dir: A path to directory where the model should be downloaded. Defaults
                to the current working directory.

        Returns:
            The absolute path to the downloaded model file.

        """
        if download_dir is None:
            download_dir = Path.cwd()
        download_dir = Path(download_dir)

        filename, url = self._teamspace_api.request_artifact_download(
            name=name,
            version="latest",  # TODO: Support version as input
        )

        download_dir.mkdir(parents=True, exist_ok=True)
        download_path = download_dir / filename
        self._teamspace_api.download_artifact_file(url, download_path)
        return str(download_path.resolve())


def _resolve_valueerror_message(error: ValueError, owner: Owner, teamspace_name: str) -> ValueError:
    """Resolves the ValueError Message and replaces it with a nicer message."""
    message = error.args[0]
    if message.startswith("Teamspace") and message.endswith("does not exist"):
        entire_ts_name = f"{owner.name}/{teamspace_name}"

        if isinstance(owner, User):
            organizations = _get_organizations_for_authed_user()
            message = (
                f"Teamspace {entire_ts_name} does not exist. "
                "Is it maybe an organizational Teamspace? You are a member of the following organizations: "
                f"{[o.name for o in organizations]}. Maybe specify one of these instead "
                "of your user if the Teamspace belongs to the organization."
            )
        else:
            # organization teamspace owner
            user = User()
            message = (
                f"Teamspace {entire_ts_name} does not exist. "
                f"Is it maybe a user Teamspace. You specified org={owner.name}, "
                "but maybe the Teamspace is part of your user? "
                f"Consider specifying user={user.name} instead of your org."
            )

    return ValueError(message, *error.args[1:])
