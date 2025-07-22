from typing import TYPE_CHECKING, Dict, Optional, Union

from lightning_sdk.api.job_api import JobApiV1
from lightning_sdk.job.base import _BaseJob
from lightning_sdk.status import Status

if TYPE_CHECKING:
    from lightning_sdk.machine import CloudProvider, Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

from functools import cached_property

from lightning_sdk.job.work import Work


class _JobV1(_BaseJob):
    """Implementation to run async workloads from your Studio."""

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
                in case it is owned directly by a user instead of an org
        """
        self._job_api = JobApiV1()
        super().__init__(name=name, teamspace=teamspace, org=org, user=user, _fetch_job=_fetch_job)

    @classmethod
    def run(
        cls,
        name: str,
        machine: Union["Machine", str],
        command: str,
        studio: "Studio",
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        cloud_account: Optional[str] = None,
        cloud_provider: Optional[str] = None,
        interruptible: bool = False,
        cluster: Optional[str] = None,  # deprecated in favor of cloud_account
    ) -> "_BaseJob":
        """Start a new async workload from your studio.

        Args:
            name: the name of the job
            machine: the machine to run the workload on
            command: the command to execute
            studio: the studio the job belongs to
            teamspace: the teamspace the job is part of
            org: the organization owning the teamspace (if applicable)
            user: the user owning the teamspace (if applicable)
            cloud_account: the cloud account to run the workload on
            interruptible: whether the workload can be interrupted

        Returns:
            the created job
        """
        return super().run(
            name=name,
            machine=machine,
            command=command,
            studio=studio,
            image=None,
            teamspace=teamspace,
            org=org,
            user=user,
            cloud_account=cloud_account,
            cloud_provider=cloud_provider,
            env=None,
            interruptible=interruptible,
            image_credentials=None,
            cloud_account_auth=False,
            cluster=cluster,
            path_mappings=None,
            max_runtime=None,
        )

    def _submit(
        self,
        machine: Union["Machine", str],
        command: Optional[str] = None,
        studio: Optional["Studio"] = None,
        image: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
        cloud_account: Optional[str] = None,
        cloud_provider: Optional[Union["CloudProvider", str]] = None,
        image_credentials: Optional[str] = None,
        cloud_account_auth: bool = False,
        artifacts_local: Optional[str] = None,
        artifacts_remote: Optional[str] = None,
        entrypoint: str = "sh -c",
        path_mappings: Optional[Dict[str, str]] = None,
        max_runtime: Optional[int] = None,
    ) -> "_JobV1":
        """Submit a job to run on a machine.

        Args:
            machine: The machine to run the job on.
            command: The command to execute.
            studio: The studio the job belongs to.
            image: The image to use for the job (not supported).
            env: The environment variables for the job (not supported).
            interruptible: Whether the job can be interrupted.
            cloud_account: The cloud account to run the job on.
            image_credentials: The image credentials for the job (not supported).
            cloud_account_auth: Whether to use cloud account authentication for the job (not supported).
            entrypoint: The entrypoint of your docker container (not supported).
                Defaults to `sh -c` which just runs the provided command in a standard shell.
                To use the pre-defined entrypoint of the provided image, set this to an empty string.
                Only applicable when submitting docker jobs.
            path_mappings: The mappings from data connection inside your container (not supported)
            max_runtime: the duration (in seconds) for which to allocate the machine.
                Irrelevant for most machines, required for some of the top-end machines on GCP.
                If in doubt, set it. Won't have an effect on machines not requiring it.
                Defaults to 3h

        Returns:
            The submitted job.

        """
        raise NotImplementedError("Cannot submit new jobs with JobsV1!")

    def _update_internal_job(self) -> None:
        try:
            self._job = self._job_api.get_job(self._name, self.teamspace.id)
        except ValueError as e:
            raise ValueError(f"Job {self._name} does not exist in Teamspace {self.teamspace.name}") from e

    @property
    def status(self) -> "Status":
        """Returns the status of the job."""
        try:
            status = self._job_api.get_job_status(self._job.id, self.teamspace.id)
            return _internal_status_to_external_status(status)
        except Exception:
            raise RuntimeError(
                f"Job {self._name} does not exist in Teamspace {self.teamspace.name}. Did you delete it?"
            ) from None

    def stop(self) -> None:
        """Stops the job. is blocking until the ob is stopped."""
        if self.status in (Status.Stopped, Status.Completed, Status.Failed):
            return None

        return self._job_api.stop_job(self._job.id, self.teamspace.id)

    def delete(self) -> None:
        """Deletes the job.

        Caution: this also deletes all artifacts created by the job.
        """
        self._job_api.delete_job(self._job.id, self.teamspace.id)

    @cached_property
    def work(self) -> Work:
        """Get the work associated with the job."""
        _work = self._job_api.list_works(self._job.id, self.teamspace.id)
        if len(_work) == 0:
            raise ValueError("No works found for job")
        return Work(_work[0].id, self, self.teamspace)

    @property
    def machine(self) -> Union["Machine", str]:
        """Get the machine the job is running on."""
        return self.work.machine

    @property
    def name(self) -> str:
        """The name of the job."""
        return self._job.name

    @property
    def artifact_path(self) -> Optional[str]:
        """The path to the artifacts of the job in the distributed teamspace filesystem."""
        return self.work.artifact_path

    @property
    def snapshot_path(self) -> Optional[str]:
        """The path to the snapshot of the job in the distributed teamspace filesystem."""
        return f"/teamspace/jobs/{self.name}/snapshot"

    @property
    def share_path(self) -> Optional[str]:
        """The path to the share of the job in the distributed teamspace filesystem."""
        return f"/teamspace/jobs/{self.name}/share"

    @property
    def logs(self) -> str:
        """The logs of the job."""
        return self.work.logs

    @property
    def image(self) -> Optional[str]:
        """The image used to submit the job."""
        # jobsv1 don't support images, so return None here
        return None

    @property
    def studio(self) -> Optional["Studio"]:
        """The studio used to submit the job."""
        from lightning_sdk.studio import Studio

        studio_name = self._job_api.get_studio_name(self._guaranteed_job)
        return Studio(studio_name, teamspace=self.teamspace)

    @property
    def command(self) -> str:
        """The command the job is running."""
        return self._job_api.get_command(self._guaranteed_job)

    # the following and functions are solely to make the Work class function
    @property
    def _id(self) -> str:
        return self._guaranteed_job.id

    def _name_filter(self, name: str) -> str:
        return name.replace("root.", "")


def _internal_status_to_external_status(internal_status: str) -> "Status":
    """Converts internal status strings from HTTP requests to external enums."""
    return {
        # don't get a status if no instance alive
        None: Status.Stopped,
        # TODO: should we have deleted in here?
        "LIGHTNINGAPP_INSTANCE_STATE_UNSPECIFIED": Status.Pending,
        "LIGHTNINGAPP_INSTANCE_STATE_IMAGE_BUILDING": Status.Pending,
        "LIGHTNINGAPP_INSTANCE_STATE_NOT_STARTED": Status.Pending,
        "LIGHTNINGAPP_INSTANCE_STATE_PENDING": Status.Pending,
        "LIGHTNINGAPP_INSTANCE_STATE_RUNNING": Status.Running,
        "LIGHTNINGAPP_INSTANCE_STATE_FAILED": Status.Failed,
        "LIGHTNINGAPP_INSTANCE_STATE_STOPPED": Status.Stopped,
        "LIGHTNINGAPP_INSTANCE_STATE_COMPLETED": Status.Completed,
    }[internal_status]
