import glob
import os
import warnings
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

from tqdm.auto import tqdm

import lightning_sdk
from lightning_sdk.agents import Agent
from lightning_sdk.api import CloudAccountApi, SecretType, TeamspaceApi
from lightning_sdk.api.utils import AccessibleResource, Experiment, raise_access_error_if_not_allowed
from lightning_sdk.lightning_cloud.openapi import (
    V1ClusterType,
    V1Model,
    V1ModelVersionArchive,
    V1ProjectClusterBinding,
)
from lightning_sdk.machine import CloudProvider, Machine
from lightning_sdk.models import UploadedModelInfo
from lightning_sdk.organization import Organization
from lightning_sdk.owner import Owner
from lightning_sdk.user import User
from lightning_sdk.utils.logging import TrackCallsMeta
from lightning_sdk.utils.resolve import (
    _get_organizations_for_authed_user,
    _parse_model_and_version,
    _resolve_org,
    _resolve_teamspace_name,
    _resolve_user,
    skip_studio_init,
)

if TYPE_CHECKING:
    from lightning_sdk.job import Job
    from lightning_sdk.mmt import MMT
    from lightning_sdk.studio import VM, Studio


class FolderLocation(Enum):
    """Cloud provider location for a Teamspace folder."""

    AWS = "AWS"
    GCP = "GCP"
    CLOUD_AGNOSTIC = "CLOUD_AGNOSTIC"

    def __str__(self) -> str:
        """Converts the FolderLocation to a str.

        Returns:
            str: The string value of the enum member (e.g. ``"AWS"``).
        """
        return self.value


class ConnectionType(Enum):
    """Type of external data source that can be connected to a Teamspace."""

    EFS = "EFS"
    S3 = "S3"
    GCS = "GCS"
    FILESTORE = "FILESTORE"

    def __str__(self) -> str:
        """Converts the ConnectionType to a str.

        Returns:
            str: The string value of the enum member (e.g. ``"EFS"``).
        """
        return self.value


class Teamspace(metaclass=TrackCallsMeta):
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
        self._cloud_account_api = CloudAccountApi()

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

        # If still no user or org resolved, try config defaults
        if self._user is None and self._org is None:
            from lightning_sdk.utils.config import Config, DefaultConfigKeys

            config = Config()
            owner_type = config.get_value(DefaultConfigKeys.teamspace_owner_type)
            owner_name = config.get_value(DefaultConfigKeys.teamspace_owner)

            if owner_type and owner_name:
                if owner_type.lower() == "organization":
                    self._org = _resolve_org(owner_name)
                elif owner_type.lower() == "user":
                    self._user = _resolve_user(owner_name)

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
        """The teamspace's name.

        Returns:
            str: The name of this teamspace.
        """
        return self._teamspace.name

    @property
    def id(self) -> str:
        """The teamspace's ID.

        Returns:
            str: The unique identifier of this teamspace.
        """
        return self._teamspace.id

    @property
    def owner(self) -> Owner:
        """The teamspace's owner.

        Returns:
            Owner: The owning :class:`~lightning_sdk.owner.Owner` (user or org).
        """
        return self._owner

    @property
    def studios(self) -> List["Studio"]:
        """All studios within that teamspace.

        Returns:
            List[Studio]: Every Studio belonging to this teamspace.
        """
        raise_access_error_if_not_allowed(AccessibleResource.Studios, self.id)
        from lightning_sdk.studio import Studio

        return self._get_studios(Studio)

    @property
    def vms(self) -> List["VM"]:
        """All VMs within this teamspace.

        Returns:
            list[VM]: The VMs belonging to this teamspace.

        Raises:
            PermissionError: If the authenticated user cannot access Studios in this teamspace.
        """
        try:
            raise_access_error_if_not_allowed(AccessibleResource.Studios, self.id)
        except PermissionError as e:
            raise PermissionError(str(e).replace("Studios", "VMs")) from e
        from lightning_sdk.studio import VM

        return [x for x in self._get_studios(VM) if isinstance(x, VM)]

    def _get_studios(self, target_cls: type) -> List[Union["Studio", "VM"]]:
        studios = []
        cloud_accounts = self._teamspace_api.list_cloud_accounts(teamspace_id=self.id)
        for cl in cloud_accounts:
            _studios = self._teamspace_api.list_studios(teamspace_id=self.id, cloud_account=cl.cluster_id)
            for s in _studios:
                with skip_studio_init():
                    studio = target_cls(name=s.name, teamspace=self, create_ok=False)
                    studio._studio = s
                    studio._teamspace = self
                    studios.append(studio)

        return studios

    @property
    def default_cloud_account(self) -> Optional[str]:
        """The default cloud account for this teamspace.

        Falls back to the owning organization's preferred cloud account when the teamspace has none set.

        Returns:
            str | None: The preferred cloud account ID, or None if not configured.
        """
        owner_preferred_cluster = (
            getattr(self.owner, "default_cloud_account", None) if isinstance(self.owner, Organization) else None
        )
        return self._teamspace.project_settings.preferred_cluster or owner_preferred_cluster

    @property
    def start_studios_on_interruptible(self) -> bool:
        """Whether new Studios in this teamspace start on interruptible (spot) instances by default.

        Returns:
            bool: True if Studios default to interruptible instances.
        """
        return self._teamspace.project_settings.start_studio_on_spot_instance

    @property
    def cloud_accounts(self) -> List[str]:
        """All cloud accounts associated with that teamspace.

        Returns:
            List[str]: The cloud account names for this teamspace.
        """
        cloud_accounts = self._teamspace_api.list_cloud_accounts(teamspace_id=self.id)
        return [cl.cluster_name for cl in cloud_accounts]

    @property
    def cloud_account_objs(self) -> List[V1ProjectClusterBinding]:
        """All cloud accounts associated with that teamspace.

        Returns:
            List[V1ProjectClusterBinding]: The raw cloud account binding objects for this teamspace.
        """
        return self._teamspace_api.list_cloud_accounts(teamspace_id=self.id)

    @property
    def clusters(self) -> List[str]:
        """All clusters associated with that teamspace.

        Returns:
            List[str]: The cluster names for this teamspace. Deprecated — use :attr:`cloud_accounts` instead.
        """
        warnings.warn(
            "The 'clusters' attribute is deprecated and will be removed in the future. "
            "Please use the 'cloud_accounts' attribute instead.",
            DeprecationWarning,
        )
        return self.cloud_accounts

    @property
    def jobs(self) -> Tuple["Job", ...]:
        """All single-machine jobs in this teamspace.

        Returns:
            tuple[Job, ...]: Every Job belonging to this teamspace.

        Raises:
            PermissionError: If the authenticated user cannot access Jobs in this teamspace.
        """
        from lightning_sdk.job import Job
        from lightning_sdk.plugin import forced_v1

        raise_access_error_if_not_allowed(AccessibleResource.Jobs, self.id)

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
        """All multi-machine training jobs in this teamspace.

        Returns:
            tuple[MMT, ...]: Every MMT job belonging to this teamspace.

        Raises:
            PermissionError: If the authenticated user cannot access Jobs in this teamspace.
        """
        from lightning_sdk.mmt import MMT
        from lightning_sdk.plugin import forced_v1

        raise_access_error_if_not_allowed(AccessibleResource.Jobs, self.id)

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

    @property
    def secrets(self) -> Dict[str, str]:
        """All (encrypted) secrets for the teamspace.

        Note:
            Once created, the secret values are encrypted and cannot be viewed here anymore.

        Returns:
            Dict[str, str]: A mapping of secret names to their (encrypted) values.
        """
        return self._teamspace_api.get_secrets(self.id)

    def set_secret(self, key: str, value: str, secret_type: Union[str, SecretType] = SecretType.GENERIC) -> None:
        """Set an encrypted secret for the teamspace.

        Args:
            key: Secret name. Must start with a letter or underscore and contain only
                alphanumeric characters and underscores.
            value: The secret value to store.
            secret_type: The type of secret, either a ``SecretType`` member or its string
                value. Defaults to ``SecretType.GENERIC``. Use ``SecretType.HF_TOKEN``
                (or ``"hf_token"``) to tag the secret as a HuggingFace access token so it
                can be referenced via ``Deployment.start(hf_token_secret=...)``. The type
                is only applied when the secret is created; updating an existing secret
                leaves its type unchanged.

        Raises:
            ValueError: If ``key`` contains invalid characters or ``secret_type`` is invalid.
        """
        if not self._teamspace_api.verify_secret_name(key):
            raise ValueError(
                "Secret keys must only contain alphanumeric characters and underscores and not begin with a number."
            )

        self._teamspace_api.set_secret(self.id, key, value, secret_type=secret_type)

    def list_machines(self, cloud_account: Optional[str] = None, machine: Optional[str] = None) -> List[Machine]:
        """List available machines across cloud accounts.

        Args:
            cloud_account: The cloud account from which to list available machines. If None, uses LIGHTNING_CLUSTER_ID
                environment variable. If that's also None, queries all global cloud accounts.
            machine: Specific machine name to filter by. If provided, only returns that
                machine type. Must be a valid Machine enum value.

        Returns:
            List of available machines, excluding out-of-capacity machines.

        Raises:
            RuntimeError: If no cloud account can be resolved.
            ValueError: If the provided machine name is not a valid Machine value.
        """
        if cloud_account is None:
            cloud_account = os.getenv("LIGHTNING_CLUSTER_ID", None)

        # if cloud_account is not given as a paramter and as a env var, use global cloud_accounts
        if cloud_account is None:
            global_cloud_accounts = self._cloud_account_api.list_global_cloud_accounts(teamspace_id=self.id)
            cloud_accounts = [cm.id for cm in global_cloud_accounts]
        else:
            cloud_accounts = [cloud_account]

        if cloud_accounts is None:
            raise RuntimeError("Could not resolve cloud account")

        if machine:
            _machine_values = tuple(
                [
                    machine.name
                    for machine in Machine.__dict__.values()
                    if isinstance(machine, Machine) and machine._include_in_cli
                ]
            )
            if machine not in _machine_values:
                raise ValueError(f"Machine '{machine}' is not valid. Valid machines are: {_machine_values}")
            machine = getattr(Machine, machine.upper(), Machine(machine, machine))

        cloud_machines = self._teamspace_api.list_machines(
            self.id, cloud_accounts=cloud_accounts, machine=machine, org_id=self._org.id
        )
        # filter out of capacity machines
        cloud_machines = [cm for cm in cloud_machines if not cm.out_of_capacity]
        return [
            Machine(
                name=cluster_machine.instance_id,
                slug=cluster_machine.slug_multi_cloud,
                instance_type=cluster_machine.instance_id,
                family=cluster_machine.family,
                accelerator_count=cluster_machine.resources.gpu or cluster_machine.resources.cpu,
                cost=cluster_machine.cost,
                interruptible_cost=cluster_machine.spot_price,
                provider=cluster_machine.provider,
                wait_time=float(cluster_machine.available_in_seconds) if cluster_machine.available_in_seconds else None,
                interruptible_wait_time=float(cluster_machine.available_in_seconds_spot)
                if cluster_machine.available_in_seconds_spot
                else None,
            )
            for cluster_machine in cloud_machines
        ]

    def __eq__(self, other: "Teamspace") -> bool:
        """Checks whether the provided other object is equal to this one.

        Args:
            other: The other Teamspace to compare against.

        Returns:
            bool: True if both Teamspaces share the same name, id, and owner.
        """
        return (
            type(self) is type(other) and self.name == other.name and self.id == other.id and self.owner == other.owner
        )

    def __repr__(self) -> str:
        """Returns reader friendly representation.

        Returns:
            str: A string of the form ``Teamspace(name=..., owner=...)``.
        """
        return f"Teamspace(name={self.name}, owner={self.owner!r})"

    def __str__(self) -> str:
        """Returns reader friendly representation.

        Returns:
            str: Same value as :meth:`__repr__`.
        """
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
        """Create a new AI agent backed by a custom model endpoint.

        Args:
            name: Display name for the agent.
            api_key: API key used to authenticate requests to the model endpoint.
            base_url: Base URL of the model endpoint (e.g. an OpenAI-compatible server).
            model: Model identifier to use (e.g. ``"gpt-4o"``).
            org_id: Optional organization ID to associate with the agent. Defaults to ``""``.
            prompt_template: System prompt template shown to the model. Defaults to ``""``.
            description: Human-readable description of the agent. Defaults to ``""``.
            prompt_suggestions: Suggested user prompts shown in the chat UI. Defaults to None.
            file_uploads_enabled: Whether the agent accepts file uploads from users. Defaults to None.

        Returns:
            Agent: The newly created agent.
        """
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
        path: Union[str, Path, List[Union[str, Path]]],
        name: str,
        version: Optional[str] = None,
        cloud_account: Optional[str] = None,
        progress_bar: bool = True,
        metadata: Optional[dict] = None,
        experiment: Optional[Experiment] = None,
    ) -> UploadedModelInfo:
        """Upload a local checkpoint file to the model store.

        Args:
            path: Path to the model file or folder to upload.
            name: Name tag of the model to upload.
            version: Version tag of the model to upload.
                If not provided, the ``vX`` version will be used where X is running index.
            cloud_account: The name of the cloud account to store the Model in.
                If not provided, the default cloud account for the Teamspace will be used.
            progress_bar: Whether to show a progress bar for the upload.
            metadata: Metadata to attach to the model. Can be a dictionary.
            experiment: The experiment producing this model.

        Returns:
            UploadedModelInfo: An object describing the uploaded model (name, version, teamspace, cloud_account).

        Raises:
            ValueError: If no path or name is provided, or if metadata is not a dict.
            FileNotFoundError: If the path contains no files.
            RuntimeError: If multiple paths resolve to conflicting relative paths.
            TypeError: If metadata is not a dictionary.
        """
        raise_access_error_if_not_allowed(AccessibleResource.Models, self.id)
        if not path:
            raise ValueError("No path provided to upload")
        if not name:
            raise ValueError("No name provided for the model")

        if isinstance(path, (str, Path)):
            path = [path]
        file_paths, relative_paths = [], []
        for p in path:
            lpaths, rpaths = _list_files(p)
            file_paths.extend(lpaths)
            relative_paths.extend(rpaths)

        if not file_paths:
            raise FileNotFoundError(
                "The path to upload doesn't contain any files. Make sure it points to a file or"
                f" non-empty folder: {path}"
            )
        if len(relative_paths) != len(set(relative_paths)):
            raise RuntimeError(
                "The paths to upload contain files with the same name or relative path in folders."
                f"The listed files are: {file_paths}\nThe relative paths are: {relative_paths}"
            )

        if cloud_account is None:
            cloud_account = self._teamspace_api._determine_cloud_account(self.id)
        if not metadata:
            metadata = {}
        if not isinstance(metadata, dict):
            raise TypeError(f"Metadata must be a dictionary, but provided {type(metadata)}")
        metadata.update({"lightning-sdk": lightning_sdk.__version__})

        model = self._teamspace_api.create_model(
            name=name,
            version=version,
            metadata=metadata,
            private=True,
            teamspace_id=self.id,
            cloud_account=cloud_account,
            experiment=experiment,
        )
        self._teamspace_api.upload_model_files(
            model_id=model.model_id,
            version=model.version,
            file_paths=file_paths,
            remote_paths=relative_paths,
            teamspace_id=self.id,
            progress_bar=progress_bar,
        )
        self._teamspace_api._complete_model_upload(
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

        Raises:
            ValueError: If no model name is provided.
            RuntimeError: If the model upload is not yet complete or no files were downloaded.
        """
        raise_access_error_if_not_allowed(AccessibleResource.Models, self.id)
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
        raise_access_error_if_not_allowed(AccessibleResource.Models, self.id)
        name, version = _parse_model_and_version(name)
        self._teamspace_api.delete_model(name=name, version=version, teamspace_id=self.id)

    def list_models(self) -> List[V1Model]:
        """List all models in the model store.

        Returns:
            List[V1Model]: All models stored in this teamspace's model store.
        """
        raise_access_error_if_not_allowed(AccessibleResource.Models, self.id)
        return self._teamspace_api.list_models(teamspace_id=self.id)

    def list_model_versions(self, name: str) -> List[V1ModelVersionArchive]:
        """List all versions of a model in the model store.

        Args:
            name: The model name to list versions for. Must not include a version tag (no colon).

        Returns:
            List[V1ModelVersionArchive]: All available versions of the specified model.

        Raises:
            ValueError: If ``name`` contains a colon (version tag).
            PermissionError: If the authenticated user cannot access Models in this teamspace.
        """
        raise_access_error_if_not_allowed(AccessibleResource.Models, self.id)
        if ":" in name:
            raise ValueError(
                "Model name should not contain a version tag. Please provide the model name without a version."
            )
        return self._teamspace_api.list_model_versions(teamspace_id=self.id, model_name=name)

    def upload_file(
        self,
        file_path: Union[Path, str],
        remote_path: Optional[str] = None,
        progress_bar: bool = True,
        cloud_account: Optional[str] = None,
    ) -> None:
        """Upload a file to the Teamspace drive.

        Args:
            file_path: Local path of the file to upload.
            remote_path: Destination path inside the Teamspace drive. Defaults to the file's basename.
            progress_bar: Whether to display a progress bar. Defaults to ``True``.
            cloud_account: Cloud account to use for storage. Defaults to the teamspace default.
        """
        if remote_path is None:
            remote_path = os.path.split(file_path)[1]

        if cloud_account is None:
            warnings.warn(
                f"No cloud account specified. Using teamspace default cloud account: {self.default_cloud_account}."
            )
            cloud_account = self.default_cloud_account

        self._teamspace_api.upload_file(
            teamspace_id=self._teamspace.id,
            cloud_account=cloud_account,
            file_path=file_path,
            remote_path=os.path.normpath(remote_path),
            progress_bar=progress_bar,
        )

    def upload_folder(
        self,
        folder_path: str,
        remote_path: Optional[str] = None,
        progress_bar: bool = True,
        cloud_account: Optional[str] = None,
    ) -> None:
        """Upload a local directory to the Teamspace drive.

        Args:
            folder_path: Local directory to upload.
            remote_path: Destination directory inside the Teamspace drive.
            progress_bar: Whether to display a progress bar. Defaults to ``True``.
            cloud_account: Cloud account to use for storage. Defaults to the teamspace default.

        Raises:
            ValueError: If ``folder_path`` is ``None``.
            NotADirectoryError: If ``folder_path`` is a file or does not exist.
        """
        if folder_path is None:
            raise ValueError("Cannot upload a folder that is None.")
        folder_path = os.path.normpath(folder_path)
        if os.path.isfile(folder_path):
            raise NotADirectoryError(f"Cannot upload a file as a folder. '{folder_path}' is a file.")
        if not os.path.exists(folder_path):
            raise NotADirectoryError(f"Cannot upload a folder that does not exist. '{folder_path}' is not a directory.")
        all_files = []
        for fp in glob.glob(os.path.join(folder_path, "**"), recursive=True):
            if not os.path.isfile(fp):
                continue
            rel_path = os.path.relpath(fp, folder_path)
            remote_file = os.path.join(remote_path, rel_path) if remote_path else rel_path
            all_files.append((fp, remote_file))

        if progress_bar:
            progress_bar = tqdm(total=len(all_files), desc="Uploading files", unit="file")
        for local_file, remote_path in sorted(all_files, key=lambda p: p[1]):
            if progress_bar:
                progress_bar.set_description(f"Uploading {local_file}")
            self.upload_file(local_file, remote_path=remote_path, progress_bar=False, cloud_account=cloud_account)
            if progress_bar:
                progress_bar.update(1)
        if progress_bar:
            progress_bar.close()

    def download_file(
        self, remote_path: str, file_path: Optional[str] = None, cloud_account: Optional[str] = None
    ) -> None:
        """Download a file from the Teamspace drive to a local path.

        Args:
            remote_path: Path of the file inside the Teamspace drive.
            file_path: Local destination path. Defaults to ``remote_path``.
            cloud_account: Cloud account to use. Defaults to ``None``.
        """
        if file_path is None:
            file_path = remote_path

        self._teamspace_api.download_file(
            path=remote_path,
            target_path=file_path,
            teamspace_id=self._teamspace.id,
            cloud_account=cloud_account,
        )

    def download_folder(
        self, remote_path: str, target_path: Optional[str] = None, cloud_account: Optional[str] = None
    ) -> None:
        """Download a directory from the Teamspace drive to a local path.

        Args:
            remote_path: Path of the directory inside the Teamspace drive.
            target_path: Local destination directory. Defaults to ``remote_path``.
            cloud_account: Cloud account to use. Defaults to ``None``.
        """
        if target_path is None:
            target_path = remote_path

        self._teamspace_api.download_folder(
            path=remote_path,
            target_path=target_path,
            teamspace_id=self._teamspace.id,
            cloud_account=cloud_account,
        )

    def new_folder(
        self, name: str, location: Optional[FolderLocation] = None, cloud_account: Optional[str] = None
    ) -> None:
        """Create a new folder in this Teamspace.

        Args:
            name: The name of the folder. Folders will be accesible under `/teamspace/folders/<name>`
            location: The location of the folder. Defaults to cloud agnostic.
            cloud_account: The cloud account to create the folder in. Not used for cloud agnostic folders.

        Raises:
            ValueError: If the specified cloud account cannot be found in this teamspace.
        """
        if cloud_account is None:
            cloud_account = self.default_cloud_account

        cloud_accounts = self._cloud_account_api.list_cloud_accounts(self.id)
        resolved_cloud_accounts = [
            external_cloud for external_cloud in cloud_accounts if external_cloud.id == cloud_account
        ]

        if len(resolved_cloud_accounts) == 0:
            raise ValueError(f"Cloud account not found: {cloud_account}")

        resolved_cloud_account = resolved_cloud_accounts[0]

        # if the cloud account is global, default to agnostic
        if location is None and resolved_cloud_account.spec.cluster_type == V1ClusterType.GLOBAL:
            location = FolderLocation.CLOUD_AGNOSTIC

        # if it's global, then default to agnostic, and aws / gcp otherwise if set
        if (
            location is not None
            and location != FolderLocation.CLOUD_AGNOSTIC
            and resolved_cloud_account.spec.cluster_type == V1ClusterType.GLOBAL
        ):
            providers = self._cloud_account_api.get_cloud_account_provider_mapping(self.id)

            if location == FolderLocation.AWS:
                resolved_cloud_account = providers[CloudProvider.AWS]
            elif location == FolderLocation.GCP:
                resolved_cloud_account = providers[CloudProvider.GCP]

        if location == FolderLocation.CLOUD_AGNOSTIC:
            self._teamspace_api.new_folder(self.id, name, None)
        else:
            self._teamspace_api.new_folder(self.id, name, resolved_cloud_account)

        return

    def new_connection(
        self,
        name: str,
        source: str,
        connection_type: ConnectionType,
        writable: bool = True,
        cloud_account: Optional[str] = None,
        region: Optional[str] = None,
    ) -> None:
        """Add an existing data source to this Teamspace.

        Args:
          name: the name under which your data will be available in this Teamspace
          source: the source spec of your data. Format depends on the type of data to connect.
            For EFS, this should be the filsystem id
          connection_type: the kind of data to connect to this Teamspace
          writable: whether to support write-back to this data source. If False, the data is connected as read-only
          cloud_account: which cloud-account to connect to the data source to.
            If not specified, will retrieve the cloud-account that matches the required provider type
            starting with private cloud accounts and falling back to public if necessary.
          region: which provider region this data is in. Required for some connection types only.

        Raises:
            ValueError: If region is not specified for EFS connections, or if the resolved cloud account is not found.
        """
        provider_for_connection = self._cloud_account_api.get_cloud_provider_for_connection_type(connection_type)

        if connection_type == ConnectionType.EFS and region is None:
            raise ValueError("Region must be specified")

        cloud_account = self._cloud_account_api.resolve_cloud_account(
            self.id,
            cloud_account=cloud_account,
            cloud_provider=provider_for_connection,
            default_cloud_account=None,
        )

        cloud_accounts = self._cloud_account_api.list_cloud_accounts(self.id)
        resolved_cloud_accounts = [
            external_cloud for external_cloud in cloud_accounts if external_cloud.id == cloud_account
        ]

        if len(resolved_cloud_accounts) == 0:
            raise ValueError(f"Cloud account not found: {cloud_account}")

        resolved_cloud_account = resolved_cloud_accounts[0]

        self._teamspace_api.new_connection(self.id, name, source, resolved_cloud_account, writable, region or "")


def _list_files(path: Union[str, Path]) -> Tuple[List[Path], List[str]]:
    """List all folders in a directory and return them as a list and relative path.

    Args:
        path: The local file or directory path to enumerate.

    Returns:
        Tuple[List[Path], List[str]]: A tuple of (absolute paths, relative path strings).

    Raises:
        FileNotFoundError: If the given path does not exist.
    """
    path = Path(path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Path {path} does not exist")
    if not path.is_dir():
        return [path], [str(path.name)]
    local_paths = [p for p in path.rglob("*") if p.is_file()]
    relative_paths = [str(p.relative_to(path)) for p in local_paths]
    return local_paths, relative_paths


def _resolve_valueerror_message(error: ValueError, owner: Owner, teamspace_name: str) -> ValueError:
    """Resolves the ValueError Message and replaces it with a nicer message.

    Args:
        error: The original ValueError raised during teamspace resolution.
        owner: The owner (user or org) used in the lookup.
        teamspace_name: The name of the teamspace that could not be found.

    Returns:
        ValueError: A new ValueError with a more descriptive message.
    """
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
