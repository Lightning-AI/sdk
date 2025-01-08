from contextlib import suppress
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Union

from lightning_sdk.api.user_api import UserApi
from lightning_sdk.job.job import _has_jobs_v2
from lightning_sdk.mmt.base import MMTMachine, _BaseMMT
from lightning_sdk.mmt.v1 import _MMTV1
from lightning_sdk.mmt.v2 import _MMTV2
from lightning_sdk.utils.resolve import _setup_logger

if TYPE_CHECKING:
    from lightning_sdk.machine import Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.status import Status
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

_logger = _setup_logger(__name__)


@lru_cache(maxsize=None)
def _has_mmt_v2() -> bool:
    # users need both mmtv2 and jobsv2 flags in order for mmtv2 to work correctly
    if not _has_jobs_v2():
        return False

    api = UserApi()
    try:
        return api._get_feature_flags().mmt_v2
    except Exception:
        return False


class MMT(_BaseMMT):
    """Class to submit and manage multi-machine jobs on the Lightning AI Platform."""

    _force_v1: (
        bool
    ) = False  # required for studio plugin still working correctly as v2 currently does not support the studio env

    def __init__(
        self,
        name: str,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        *,
        _fetch_job: bool = True,
    ) -> None:
        """Fetch already existing jobs.

        Args:
            name: the name of the job
            teamspace: the teamspace the job is part of
            org: the name of the organization owning the :param`teamspace` in case it is owned by an org
            user: the name of the user owning the :param`teamspace`
                in case it is owned directly by a user instead of an org.
        """
        internal_mmt_cls = _MMTV2 if _has_mmt_v2() and not self._force_v1 else _MMTV1

        self._internal_mmt = internal_mmt_cls(
            name=name,
            teamspace=teamspace,
            org=org,
            user=user,
            _fetch_job=_fetch_job,
        )

    @classmethod
    def run(
        cls,
        name: str,
        num_machines: int,
        machine: "Machine",
        command: Optional[str] = None,
        studio: Union["Studio", str, None] = None,
        image: Union[str, None] = None,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        cloud_account: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
        image_credentials: Optional[str] = None,
        cloud_account_auth: bool = False,
        artifacts_local: Optional[str] = None,
        artifacts_remote: Optional[str] = None,
        cluster: Optional[str] = None,  # deprecated in favor of cloud_account
    ) -> "MMT":
        """Run async workloads using a docker image across multiple machines.

        Args:
            name: The name of the job. Needs to be unique within the teamspace.
            machine: The machine type to run the job on. One of {", ".join(_MACHINE_VALUES)}.
            num_machine: The number of machines to run on.
            command: The command to run inside your job. Required if using a studio. Optional if using an image.
                If not provided for images, will run the container entrypoint and default command.
            studio: The studio env to run the job with. Mutually exclusive with image.
            image: The docker image to run the job with. Mutually exclusive with studio.
            teamspace: The teamspace the job should be associated with. Defaults to the current teamspace.
            org: The organization owning the teamspace (if any). Defaults to the current organization.
            user: The user owning the teamspace (if any). Defaults to the current user.
            cloud_account: The cloud account to run the job on.
                Defaults to the studio cloud account if running with studio compute env.
                If not provided will fall back to the teamspaces default cloud account.
            env: Environment variables to set inside the job.
            interruptible: Whether the job should run on interruptible instances. They are cheaper but can be preempted.
            image_credentials: The credentials used to pull the image. Required if the image is private.
                This should be the name of the respective credentials secret created on the Lightning AI platform.
            cloud_account_auth: Whether to authenticate with the cloud account to pull the image.
                Required if the registry is part of a cloud provider (e.g. ECR).
            artifacts_local: The path of inside the docker container, you want to persist images from.
                CAUTION: When setting this to "/", it will effectively erase your container.
                Only supported for jobs with a docker image compute environment.
            artifacts_remote: The remote storage to persist your artifacts to.
                Should be of format <CONNECTION_TYPE>:<CONNECTION_NAME>:<PATH_WITHIN_CONNECTION>.
                PATH_WITHIN_CONNECTION hereby is a path relative to the connection's root.
                E.g. efs:data:some-path would result in an EFS connection named `data` and to the path `some-path`
                within it.
                Note that the connection needs to be added to the teamspace already in order for it to be found.
                Only supported for jobs with a docker image compute environment.
        """
        ret_val = super().run(
            name=name,
            num_machines=num_machines,
            machine=machine,
            command=command,
            studio=studio,
            image=image,
            teamspace=teamspace,
            org=org,
            user=user,
            cloud_account=cloud_account,
            env=env,
            interruptible=interruptible,
            image_credentials=image_credentials,
            cloud_account_auth=cloud_account_auth,
            artifacts_local=artifacts_local,
            artifacts_remote=artifacts_remote,
            cluster=cluster,  # deprecated in favor of cloud_account
        )
        # required for typing with "MMT"
        assert isinstance(ret_val, cls)

        msg = "Multi-Machine Job was successfully launched."

        with suppress(NotImplementedError):
            msg += f" View it at {ret_val.link}"

        _logger.info(msg)
        return ret_val

    def _submit(
        self,
        num_machines: int,
        machine: "Machine",
        command: Optional[str] = None,
        studio: Optional["Studio"] = None,
        image: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
        cloud_account: Optional[str] = None,
        image_credentials: Optional[str] = None,
        cloud_account_auth: bool = False,
        artifacts_local: Optional[str] = None,
        artifacts_remote: Optional[str] = None,
    ) -> "MMT":
        """Submit a new multi-machine job to the Lightning AI platform.

        Args:
            num_machines: The number of machines to run on.
            machine: The machine type to run the job on. One of {", ".join(_MACHINE_VALUES)}.
            command: The command to run inside your job. Required if using a studio. Optional if using an image.
                If not provided for images, will run the container entrypoint and default command.
            studio: The studio env to run the job with. Mutually exclusive with image.
            image: The docker image to run the job with. Mutually exclusive with studio.
            env: Environment variables to set inside the job.
            interruptible: Whether the job should run on interruptible instances. They are cheaper but can be preempted.
            cloud_account: The cloud account to run the job on.
                Defaults to the studio cloud account if running with studio compute env.
                If not provided will fall back to the teamspaces default cloud account.
            image_credentials: The credentials used to pull the image. Required if the image is private.
                This should be the name of the respective credentials secret created on the Lightning AI platform.
            cloud_account_auth: Whether to authenticate with the cloud account to pull the image.
                Required if the registry is part of a cloud provider (e.g. ECR).
            artifacts_local: The path of inside the docker container, you want to persist images from.
                CAUTION: When setting this to "/", it will effectively erase your container.
                Only supported for jobs with a docker image compute environment.
            artifacts_remote: The remote storage to persist your artifacts to.
                Should be of format <CONNECTION_TYPE>:<CONNECTION_NAME>:<PATH_WITHIN_CONNECTION>.
                PATH_WITHIN_CONNECTION hereby is a path relative to the connection's root.
                E.g. efs:data:some-path would result in an EFS connection named `data` and to the path `some-path`
                within it.
                Note that the connection needs to be added to the teamspace already in order for it to be found.
                Only supported for jobs with a docker image compute environment.
        """
        self._job = self._internal_mmt._submit(
            num_machines=num_machines,
            machine=machine,
            cloud_account=cloud_account,
            command=command,
            studio=studio,
            image=image,
            env=env,
            interruptible=interruptible,
            image_credentials=image_credentials,
            cloud_account_auth=cloud_account_auth,
            artifacts_local=artifacts_local,
            artifacts_remote=artifacts_remote,
        )
        return self

    def stop(self) -> None:
        """Stops the job."""
        return self._internal_mmt.stop()

    def delete(self) -> None:
        """Deletes the job.

        Caution: This also deletes all artifacts and snapshots associated with the job.
        """
        return self._internal_mmt.delete()

    @property
    def status(self) -> "Status":
        """The current status of the job (accumulated over all machines)."""
        return self._internal_mmt.status

    @property
    def machines(self) -> Tuple[MMTMachine, ...]:
        """Returns the sub-jobs for each individual instance."""
        return self._internal_mmt.machines

    @property
    def machine(self) -> "Machine":
        """Returns the machine type this job is running on."""
        return self._internal_mmt.machine

    @property
    def artifact_path(self) -> Optional[str]:
        """Path to the artifacts created by the job within the distributed teamspace filesystem."""
        return self._internal_mmt.artifact_path

    @property
    def snapshot_path(self) -> Optional[str]:
        """Path to the studio snapshot used to create the job within the distributed teamspace filesystem."""
        return self._internal_mmt.snapshot_path

    @property
    def share_path(self) -> Optional[str]:
        """Path to the jobs share path."""
        return None

    def _update_internal_job(self) -> None:
        return self._internal_mmt._update_internal_job()

    @property
    def name(self) -> str:
        """The job's name."""
        return self._internal_mmt.name

    @property
    def teamspace(self) -> "Teamspace":
        """The teamspace the job is part of."""
        return self._internal_mmt._teamspace

    @property
    def link(self) -> str:
        return self._internal_mmt.link

    def __getattr__(self, key: str) -> Any:
        """Forward the attribute lookup to the internal job implementation."""
        try:
            return getattr(super(), key)
        except AttributeError:
            return getattr(self._internal_mmt, key)

    @property
    def _guaranteed_job(self) -> Any:
        return self._internal_mmt._guaranteed_job
