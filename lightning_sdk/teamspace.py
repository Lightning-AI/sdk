import os
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple, Union

from lightning_sdk.agents import Agent
from lightning_sdk.api import TeamspaceApi
from lightning_sdk.machine import Machine
from lightning_sdk.models import UploadedModelInfo
from lightning_sdk.organization import Organization
from lightning_sdk.owner import Owner
from lightning_sdk.user import User
from lightning_sdk.utils.resolve import (
    _get_organizations_for_authed_user,
    _parse_model_and_version,
    _resolve_org,
    _resolve_teamspace_name,
    _resolve_user,
)

if TYPE_CHECKING:
    from lightning_sdk.job import Job
    from lightning_sdk.mmt import MMT
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
        clusters = self._teamspace_api.list_cloud_accounts(teamspace_id=self.id)
        for cl in clusters:
            _studios = self._teamspace_api.list_studios(teamspace_id=self.id, cloud_account=cl.cluster_id)
            for s in _studios:
                studios.append(Studio(name=s.name, teamspace=self, cluster=cl.cluster_name, create_ok=False))

        return studios

    @property
    def default_cloud_account(self) -> str:
        return self._teamspace.project_settings.preferred_cluster

    @property
    def start_studios_on_interruptible(self) -> bool:
        return self._teamspace.project_settings.start_studio_on_spot_instance

    @property
    def cloud_accounts(self) -> List[str]:
        """All cloud accounts associated with that teamspace."""
        clusters = self._teamspace_api.list_cloud_accounts(teamspace_id=self.id)
        return [cl.cluster_name for cl in clusters]

    @property
    def clusters(self) -> List[str]:
        """All clusters associated with that teamspace."""
        warnings.warn(
            "The 'clusters' attribute is deprecated and will be removed in the future. "
            "Please use the 'cloud_accounts' attribute instead.",
            DeprecationWarning,
        )
        return self.cloud_accounts

    @property
    def jobs(self) -> Tuple["Job", ...]:
        from lightning_sdk.job import Job
        from lightning_sdk.plugin import forced_v1

        jobsv1, jobsv2 = self._teamspace_api.list_jobs(teamspace_id=self.id)

        jobs = []

        for j1 in jobsv1:
            with forced_v1(Job):
                # _fetch_job = False to prevent refetching on init since we already got it
                job = Job(name=j1.name, teamspace=self, _fetch_job=False)
            job._internal_job._job = j1
            jobs.append(job)

        for j2 in jobsv2:
            # _fetch_job = False to prevent refetching on init since we already got it
            job = Job(name=j2.name, teamspace=self, _fetch_job=False)
            job._internal_job._job = j2
            jobs.append(job)

        return tuple(jobs)

    @property
    def multi_machine_jobs(self) -> Tuple["MMT", ...]:
        from lightning_sdk.mmt import MMT
        from lightning_sdk.plugin import forced_v1

        mmtsv1, mmtsv2 = self._teamspace_api.list_mmts(teamspace_id=self.id)

        mmts = []

        for m1 in mmtsv1:
            with forced_v1(MMT):
                # _fetch_job = False to prevent refetching on init since we already got it
                mmt = MMT(name=m1.name, teamspace=self, _fetch_job=False)
            mmt._internal_mmt._job = m1
            mmts.append(mmt)

        for m2 in mmtsv2:
            # _fetch_job = False to prevent refetching on init since we already got it
            mmt = MMT(name=m2.name, teamspace=self, _fetch_job=False)
            mmt._internal_mmt._job = m2
            mmts.append(mmt)

        return tuple(mmts)

    def list_machines(self, cloud_account: Optional[str] = None) -> List[Machine]:
        if cloud_account is None:
            cloud_account = os.getenv("LIGHTNING_CLUSTER_ID") or self.default_cloud_account

        cluster_machines = self._teamspace_api.list_machines(self.id, cloud_account=cloud_account)
        return [
            Machine(
                cluster_machine.instance_id,
                cluster_machine.instance_id,
                cost=cluster_machine.cost,
                interruptible_cost=cluster_machine.spot_price,
                wait_time=float(cluster_machine.available_in_seconds) if cluster_machine.available_in_seconds else None,
                interruptible_wait_time=float(cluster_machine.available_in_seconds_spot)
                if cluster_machine.available_in_seconds_spot
                else None,
            )
            for cluster_machine in cluster_machines
        ]

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
        path: Union[str, Path],
        name: str,
        cloud_account: Optional[str] = None,
        progress_bar: bool = True,
    ) -> UploadedModelInfo:
        """Upload a local checkpoint file to the model store.

        Args:
            path: Path to the model file or folder to upload.
            name: Name tag of the model to upload.
            cloud_account: The name of the cloud account to store the Model in.
                If not provided, the default cloud account for the Teamspace will be used.
            progress_bar: Whether to show a progress bar for the upload.
        """
        if not path:
            raise ValueError("No path provided to upload")
        if not name:
            raise ValueError("No name provided for the model")
        path = Path(path).resolve()
        if not path.exists():
            raise FileNotFoundError(str(path))

        cloud_account = (
            self._teamspace_api._determine_cloud_account(self.id) if cloud_account is None else cloud_account
        )
        filepaths = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]

        if not filepaths:
            raise FileNotFoundError(
                "The path to upload doesn't contain any files. Make sure it points to a file or"
                f" non-empty folder: {path}"
            )

        root_path = path
        if len(filepaths) == 1:
            root_path = path.parent

        filenames = ",".join(str(f.relative_to(root_path)) for f in filepaths)

        model = self._teamspace_api.create_model(
            name=name,
            metadata={"filenames": filenames},
            private=True,
            teamspace_id=self.id,
            cloud_account=cloud_account,
        )
        self._teamspace_api.upload_model_files(
            model_id=model.model_id,
            version=model.version,
            root_path=root_path,
            filepaths=filepaths,
            cloud_account=cloud_account,
            teamspace_id=self.id,
            progress_bar=progress_bar,
        )
        self._teamspace_api.complete_model_upload(
            model_id=model.model_id,
            version=model.version,
            teamspace_id=self.id,
        )
        return UploadedModelInfo(
            name=name,
            version=model.version,
            teamspace=self.name,
            cloud_account=cloud_account,
        )

    def download_model(
        self,
        name: str,
        download_dir: Optional[str] = None,
        progress_bar: bool = True,
    ) -> str:
        """Download a checkpoint from the model store.

        Args:
            name: Name tag of the model to download. Can optionally also contain a version tag separated by a colon,
                 e.g. 'modelname:v1'.
            download_dir: A path to directory where the model should be downloaded. Defaults
                to the current working directory.
            progress_bar: Whether to show a progress bar for the download.

        Returns:
            The absolute path to the downloaded model file or folder.

        """
        if not name:
            raise ValueError("No name provided for the model")
        if download_dir is None:
            download_dir = Path.cwd()
        download_dir = Path(download_dir)

        name, version = _parse_model_and_version(name)
        model_version = self._teamspace_api.get_model_version(name=name, version=version, teamspace_id=self.id)
        if not model_version.upload_complete:
            raise RuntimeError(
                f"Model {name}:{version} is not fully uploaded yet. Please wait until the upload is complete."
            )
        downloaded_files = self._teamspace_api.download_model_files(
            name=name,
            version=version,
            download_dir=download_dir,
            teamspace_name=self.name,
            teamspace_owner_name=self.owner.name,
            progress_bar=progress_bar,
        )

        if not downloaded_files:
            raise RuntimeError("No files were downloaded. This shouldn't happen, please report a bug.")

        if len(downloaded_files) == 1:
            downloaded_file = Path(downloaded_files[0])
            downloaded_path = download_dir / downloaded_file.parts[0]
            return str(downloaded_path.resolve())
        return str(Path(download_dir).resolve())

    def delete_model(self, name: str) -> None:
        """Delete a model from the model store.

        Args:
            name: Name tag of the model to delete. Can optionally also contain a version tag separated by a colon,
                 e.g. 'entity/modelname:v1'.

        """
        name, version = _parse_model_and_version(name)
        self._teamspace_api.delete_model(name=name, version=version, teamspace_id=self.id)


def _resolve_valueerror_message(error: ValueError, owner: Owner, teamspace_name: str) -> ValueError:
    """Resolves the ValueError Message and replaces it with a nicer message."""
    message = error.args[0]
    if message.startswith("Teamspace") and message.endswith("does not exist"):
        entire_ts_name = f"{owner.name}/{teamspace_name}"

        if isinstance(owner, User):
            organizations = _get_organizations_for_authed_user()
            message = (
                f"Teamspace {entire_ts_name} does not exist. "
                f"Is {teamspace_name} an organizational Teamspace? You are a member of the following organizations: "
                f"{[o.name for o in organizations]}. Try specifying the `org` parameter instead "
                "of `user` if the Teamspace belongs to the organization."
            )
        else:
            # organization teamspace owner
            user = User()
            message = (
                f"Teamspace {entire_ts_name} does not exist. "
                f"Is {teamspace_name} a user Teamspace? "
                f"Consider specifying user={user.name} instead of org={owner.name}."
            )

    return ValueError(message, *error.args[1:])
