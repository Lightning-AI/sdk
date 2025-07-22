from typing import TYPE_CHECKING, Dict, Optional, Tuple, Union

from lightning_sdk.api.mmt_api import MMTApiV1
from lightning_sdk.api.utils import _get_cloud_url
from lightning_sdk.job.v1 import _internal_status_to_external_status
from lightning_sdk.job.work import Work
from lightning_sdk.status import Status

if TYPE_CHECKING:
    from lightning_sdk.machine import CloudProvider, Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

from lightning_sdk.mmt.base import _BaseMMT


class _MMTV1(_BaseMMT):
    """V1 Implementation of Multi-Machine Training."""

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
        self._job_api = MMTApiV1()
        super().__init__(name=name, teamspace=teamspace, org=org, user=user, _fetch_job=_fetch_job)

    def _submit(
        self,
        num_machines: int,
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
        entrypoint: str = "sh -c",
        path_mappings: Optional[Dict[str, str]] = None,
        max_runtime: Optional[int] = None,
        artifacts_local: Optional[str] = None,
        artifacts_remote: Optional[str] = None,
    ) -> "_MMTV1":
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
            entrypoint: The entrypoint of your docker container. Defaults to `sh -c` which
                just runs the provided command in a standard shell.
                To use the pre-defined entrypoint of the provided image, set this to an empty string.
                Only applicable when submitting docker jobs.
            path_mappings: The mappings from data connection inside your container (not supported)
            max_runtime: the duration (in seconds) for which to allocate the machine.
                Irrelevant for most machines, required for some of the top-end machines on GCP.
                If in doubt, set it. Won't have an effect on machines not requiring it.
                Defaults to 3h

        """
        raise NotImplementedError("Cannot submit new mmts with MMTV1!")

    def _update_internal_job(self) -> None:
        try:
            self._job = self._job_api.get_job(self._name, self.teamspace.id)
        except ValueError as e:
            raise ValueError(f"Job {self._name} does not exist in Teamspace {self.teamspace.name}") from e

    @property
    def machines(self) -> Tuple["Work", ...]:
        """Returns the sub-jobs for each individual instance."""
        works = self._job_api.list_works(self._guaranteed_job.id, self.teamspace.id)

        return tuple(Work(w.id, self, self.teamspace) for w in works)

    def stop(self) -> None:
        """Stops the job."""
        if self.status in (Status.Stopped, Status.Completed, Status.Failed):
            return
        self._job_api.stop_job(self._guaranteed_job.id, self.teamspace.id)

    def delete(self) -> None:
        """Deletes the job.

        Caution: This also deletes all artifacts and snapshots associated with the job.
        """
        self._job_api.delete_job(self._guaranteed_job.id, self.teamspace.id)

    @property
    def status(self) -> "Status":
        """The current status of the job."""
        try:
            status = self._job_api.get_job_status(self._job.id, self.teamspace.id)
            return _internal_status_to_external_status(status)
        except Exception:
            raise RuntimeError(
                f"MMT {self._name} does not exist in Teamspace {self.teamspace.name}. Did you delete it?"
            ) from None

    @property
    def artifact_path(self) -> Optional[str]:
        """Path to the artifacts created by the job within the distributed teamspace filesystem."""
        return f"/teamspace/jobs/{self.name}"

    @property
    def snapshot_path(self) -> Optional[str]:
        """Path to the studio snapshot used to create the job within the distributed teamspace filesystem."""
        return f"/teamspace/jobs/{self.name}/snapshot"

    @property
    def machine(self) -> Union["Machine", str]:
        """Returns the machine type this job is running on."""
        return self.machines[0].machine

    @property
    def name(self) -> str:
        """The job's name."""
        return self._name

    @property
    def teamspace(self) -> "Teamspace":
        """The teamspace the job is part of."""
        return self._teamspace

    @property
    def link(self) -> str:
        return (
            f"{_get_cloud_url()}/{self.teamspace.owner.name}/{self.teamspace.name}/studios/{self._job_api.get_studio_name(self._guaranteed_job)}/"
            f"app?app_id=mmt&app_tab=Runs&job_name={self.name}"
        )

    @property
    def image(self) -> Optional[str]:
        """The image used to submit the job."""
        # mmtv1 don't support images, so return None here
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
