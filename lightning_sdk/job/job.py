from functools import lru_cache
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from lightning_sdk.api.user_api import UserApi
from lightning_sdk.job.base import _BaseJob
from lightning_sdk.job.v1 import _JobV1
from lightning_sdk.job.v2 import _JobV2

if TYPE_CHECKING:
    from lightning_sdk.machine import Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.status import Status
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User


@lru_cache(maxsize=None)
def _has_jobs_v2() -> bool:
    api = UserApi()
    try:
        return api._get_feature_flags().jobs_v2
    except Exception:
        return False


class Job(_BaseJob):
    def __init__(
        self,
        name: str,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        *,
        _fetch_job: bool = True,
    ) -> None:
        internal_job_cls = _JobV2 if _has_jobs_v2() else _JobV1

        self._internal_job = internal_job_cls(
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
    ) -> "Job":
        """Run async workloads using a docker image or a compute environment from your studio.

        Args:
        name: The name of the job. Needs to be unique within the teamspace.
        machine: The machine type to run the job on. One of {", ".join(_MACHINE_VALUES)}.
        command: The command to run inside your job. Required if using a studio. Optional if using an image.
            If not provided for images, will run the container entrypoint and default command.
        studio: The studio env to run the job with. Mutually exclusive with image.
        image: The docker image to run the job with. Mutually exclusive with studio.
        teamspace: The teamspace the job should be associated with. Defaults to the current teamspace.
        org: The organization owning the teamspace (if any). Defaults to the current organization.
        user: The user owning the teamspace (if any). Defaults to the current user.
        cloud_account: The cloud acocunt to run the job on.
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
            cluster=cluster,
        )
        # required for typing with "Job"
        assert isinstance(ret_val, cls)
        return ret_val

    def _submit(
        self,
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
    ) -> "Job":
        """Submit a new job to the Lightning AI platform.

        Args:
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
        self._job = self._internal_job._submit(
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
        """Stops the job.

        This is blocking until the job is stopped.
        """
        return self._internal_job.stop()

    def delete(self) -> None:
        """Deletes the job.

        Caution: This also deletes all artifacts and snapshots associated with the job.
        """
        return self._internal_job.delete()

    @property
    def status(self) -> "Status":
        """The current status of the job."""
        return self._internal_job.status

    @property
    def machine(self) -> "Machine":
        """The machine type the job is running on."""
        return self._internal_job.machine

    @property
    def artifact_path(self) -> Optional[str]:
        """Path to the artifacts created by the job within the distributed teamspace filesystem."""
        return self._internal_job.artifact_path

    @property
    def snapshot_path(self) -> Optional[str]:
        """Path to the studio snapshot used to create the job within the distributed teamspace filesystem."""
        return self._internal_job.snapshot_path

    @property
    def share_path(self) -> Optional[str]:
        """Path to the jobs share path."""
        return self._internal_job.share_path

    def _update_internal_job(self) -> None:
        return self._internal_job._update_internal_job()

    @property
    def name(self) -> str:
        """The job's name."""
        return self._internal_job.name

    @property
    def teamspace(self) -> "Teamspace":
        """The teamspace the job is part of."""
        return self._internal_job._teamspace

    @property
    def cluster(self) -> Optional[str]:
        """The cluster the job is running on."""
        return self._internal_job.cluster

    def __getattr__(self, key: str) -> Any:
        """Forward the attribute lookup to the internal job implementation."""
        try:
            return getattr(super(), key)
        except AttributeError:
            return getattr(self._internal_job, key)
