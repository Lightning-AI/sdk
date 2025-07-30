from typing import TYPE_CHECKING, Dict, Optional, Tuple, Union

from lightning_sdk.api.mmt_api import MMTApiV2
from lightning_sdk.api.utils import _get_cloud_url
from lightning_sdk.status import Status
from lightning_sdk.utils.resolve import _get_org_id

if TYPE_CHECKING:
    from lightning_sdk.job.job import Job
    from lightning_sdk.machine import CloudProvider, Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

from lightning_sdk.mmt.base import _BaseMMT


class _MMTV2(_BaseMMT):
    """New implementation of Multi-Machine Training."""

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
        self._job_api = MMTApiV2()
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
        artifacts_local: Optional[str] = None,  # deprecated in favor of path_mappings
        artifacts_remote: Optional[str] = None,  # deprecated in favor of path_mappings
    ) -> "_MMTV2":
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
                If not provided and `cloud_account_provider` is set, will resolve cluster from this, else
                will fall back to the teamspaces default cloud account.
            cloud_account_provider: The provider to select the cloud-account from.
                If set, must be in agreement with the provider from the cloud_account (if specified).
                If not specified, falls backto the teamspace default cloud account.
            image_credentials: The credentials used to pull the image. Required if the image is private.
                This should be the name of the respective credentials secret created on the Lightning AI platform.
            cloud_account_auth: Whether to authenticate with the cloud account to pull the image.
                Required if the registry is part of a cloud provider (e.g. ECR).
            entrypoint: The entrypoint of your docker container. Defaults to `sh -c` which
                just runs the provided command in a standard shell.
                To use the pre-defined entrypoint of the provided image, set this to an empty string.
                Only applicable when submitting docker jobs.
            path_mappings: Dictionary of path mappings. The keys are the path inside the container whereas the value
                represents the data-connection name and the path inside that connection.
                Should be of form
                    {
                        "<CONTAINER_PATH_1>": "<CONNECTION_NAME_1>:<PATH_WITHIN_CONNECTION_1>",
                        "<CONTAINER_PATH_2>": "<CONNECTION_NAME_2>"
                    }
                If the path inside the connection is omitted it's assumed to be the root path of that connection.
                Only applicable when submitting docker jobs.
            max_runtime: the duration (in seconds) for which to allocate the machine.
                Irrelevant for most machines, required for some of the top-end machines on GCP.
                If in doubt, set it. Won't have an effect on machines not requiring it.
                Defaults to 3h
        """
        # Command is required if Studio is provided to know what to run
        # Image is mutually exclusive with Studio
        # Command is optional for Image
        # Either image or studio must be provided
        if studio is not None:
            studio_id = studio._studio.id
            if image is not None:
                raise ValueError(
                    "image and studio are mutually exclusive as both define the environment to run the job in"
                )
            if command is None:
                raise ValueError("command is required when using a studio")
        else:
            studio_id = None
            if image is None:
                raise ValueError("either image or studio must be provided")

        cloud_account = self._cloud_account_api.resolve_cloud_account(
            self._teamspace.id,
            cloud_account=cloud_account,
            cloud_provider=cloud_provider,
            default_cloud_account=self._teamspace.default_cloud_account,
        )

        submitted = self._job_api.submit_job(
            name=self.name,
            num_machines=num_machines,
            command=command,
            cloud_account=cloud_account,
            teamspace_id=self._teamspace.id,
            studio_id=studio_id,
            image=image,
            machine=machine,
            interruptible=interruptible,
            env=env,
            image_credentials=image_credentials,
            cloud_account_auth=cloud_account_auth,
            entrypoint=entrypoint,
            path_mappings=path_mappings,
            artifacts_local=artifacts_local,
            artifacts_remote=artifacts_remote,
            max_runtime=max_runtime,
        )
        self._job = submitted
        self._name = submitted.name
        return self

    @property
    def machines(self) -> Tuple["Job", ...]:
        """Returns the sub-jobs for each individual instance."""
        from lightning_sdk.job import Job

        return tuple(
            Job(name=j.name, teamspace=self.teamspace)
            for j in self._job_api.list_mmt_subjobs(self._guaranteed_job.id, self.teamspace.id)
        )

    def stop(self) -> None:
        """Stops the job."""
        if self.status in (Status.Stopped, Status.Completed, Status.Failed):
            return
        self._job_api.stop_job(job_id=self._guaranteed_job.id, teamspace_id=self._teamspace.id)

    def delete(self) -> None:
        """Deletes the job.

        Caution: This also deletes all artifacts and snapshots associated with the job.
        """
        self._job_api.delete_job(
            job_id=self._guaranteed_job.id,
            teamspace_id=self._teamspace.id,
        )

    @property
    def status(self) -> "Status":
        """The current status of the job."""
        return self._job_api._job_state_to_external(self._latest_job.state)

    @property
    def artifact_path(self) -> Optional[str]:
        """Path to the artifacts created by the job within the distributed teamspace filesystem."""
        # TODO: Since grouping for those is not done yet on the BE, we cannot yet have a unified link here
        raise NotImplementedError

    @property
    def snapshot_path(self) -> Optional[str]:
        """Path to the studio snapshot used to create the job within the distributed teamspace filesystem."""
        # TODO: Since grouping for those is not done yet on the BE, we cannot yet have a unified link here
        raise NotImplementedError

    @property
    def machine(self) -> Union["Machine", str]:
        """Returns the machine type this job is running on."""
        return self._job_api._get_job_machine_from_spec(
            self._guaranteed_job.spec,
            self.teamspace.id,
            _get_org_id(self.teamspace),
        )

    def _update_internal_job(self) -> None:
        if getattr(self, "_job", None) is None:
            self._job = self._job_api.get_job_by_name(name=self._name, teamspace_id=self._teamspace.id)
            return

        self._job = self._job_api.get_job(job_id=self._job.id, teamspace_id=self._teamspace.id)

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
        # TODO: MMT env with studio -> go to studio plugin
        return f"{_get_cloud_url()}/{self.teamspace.owner.name}/{self.teamspace.name}/jobs/{self.name}?app_id=mmt"

    @property
    def image(self) -> Optional[str]:
        """The image used to submit the job."""
        return self._job_api.get_image_name(self._guaranteed_job)

    @property
    def studio(self) -> Optional["Studio"]:
        """The studio used to submit the job."""
        from lightning_sdk.studio import Studio

        studio_name = self._job_api.get_studio_name(self._guaranteed_job)

        # if job was submitted with image, studio will be None
        if not studio_name:
            return None
        return Studio(studio_name, teamspace=self.teamspace)

    @property
    def command(self) -> str:
        """The command the job is running."""
        return self._job_api.get_command(self._guaranteed_job)

    @property
    def num_machines(self) -> int:
        """Returns the number of machines assigned to this multi-machine job."""
        return self._job_api.get_num_machines(self._guaranteed_job)
