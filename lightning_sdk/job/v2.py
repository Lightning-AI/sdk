from typing import TYPE_CHECKING, Dict, Optional, Union

from lightning_sdk.api.job_api import JobApiV2
from lightning_sdk.api.utils import _get_cloud_url
from lightning_sdk.job.base import _BaseJob
from lightning_sdk.status import Status
from lightning_sdk.utils.resolve import _get_org_id

if TYPE_CHECKING:
    from lightning_sdk.machine import CloudProvider, Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User


class _JobV2(_BaseJob):
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
        self._job_api = JobApiV2()
        super().__init__(name=name, teamspace=teamspace, org=org, user=user, _fetch_job=_fetch_job)

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
        entrypoint: str = "sh -c",
        path_mappings: Optional[Dict[str, str]] = None,
        max_runtime: Optional[int] = None,
        artifacts_local: Optional[str] = None,  # deprecated in favor of path_mappings
        artifacts_remote: Optional[str] = None,  # deprecated in favor of path_mappings
    ) -> "_JobV2":
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
            artifacts_local=artifacts_local,
            artifacts_remote=artifacts_remote,
            entrypoint=entrypoint,
            path_mappings=path_mappings,
            max_runtime=max_runtime,
        )
        self._job = submitted
        self._name = submitted.name
        return self

    def stop(self) -> None:
        """Stop the job. If the job is already stopped, this is a no-op. This is blocking until the job is stopped."""
        if self.status in (Status.Stopped, Status.Completed, Status.Failed):
            return

        self._job_api.stop_job(job_id=self._guaranteed_job.id, teamspace_id=self._teamspace.id)

    def delete(self) -> None:
        """Delete the job.

        Caution: This also deletes all artifacts created by the job.
        """
        self._job_api.delete_job(
            job_id=self._guaranteed_job.id,
            teamspace_id=self._teamspace.id,
            cloudspace_id=self._guaranteed_job.spec.cloudspace_id,
        )

    @property
    def status(self) -> "Status":
        """The current status of the job."""
        try:
            return self._job_api._job_state_to_external(self._latest_job.state)
        except Exception:
            raise RuntimeError(
                f"Job {self._name} does not exist in Teamspace {self.teamspace.name}. Did you delete it?"
            ) from None

    @property
    def machine(self) -> Union["Machine", str]:
        """The machine type the job is running on."""
        # only fetch the job it it hasn't been fetched yet as machine cannot change over time

        return self._job_api._get_job_machine_from_spec(
            self._guaranteed_job.spec,
            self.teamspace.id,
            _get_org_id(self.teamspace),
        )

    @property
    def artifact_path(self) -> Optional[str]:
        """The path to the artifacts of the job within the distributed teamspace filesystem."""
        if self._guaranteed_job.spec.image != "":
            if self._guaranteed_job.spec.artifacts_destination != "":
                splits = self._guaranteed_job.spec.artifacts_destination.split(":")
                return f"/teamspace/{splits[0]}_connections/{splits[1]}/{splits[2]}"
            return None

        return f"/teamspace/jobs/{self._guaranteed_job.name}/artifacts"

    @property
    def snapshot_path(self) -> Optional[str]:
        """The path to the snapshot of the Studio used to create the job within the distributed teamspace filesystem."""
        if self._guaranteed_job.spec.image != "":
            return None
        return f"/teamspace/jobs/{self._guaranteed_job.name}/snapshot"

    @property
    def share_path(self) -> Optional[str]:
        """The path to the share of the job within the distributed teamspace filesystem."""
        raise NotImplementedError("Not implemented yet")

    @property
    def logs(self) -> str:
        from lightning_sdk.status import Status

        if self.status not in (Status.Failed, Status.Completed, Status.Stopped):
            raise RuntimeError("Getting jobs logs while the job is pending or running is not supported yet!")

        return self._job_api.get_logs_finished(job_id=self._guaranteed_job.id, teamspace_id=self.teamspace.id)

    @property
    def link(self) -> str:
        mmt_name = self._job_api.get_mmt_name(self._guaranteed_job)

        if self._job_api.get_image_name(self._guaranteed_job):
            if mmt_name:
                # don't go via the studio unless we use studio env
                return (
                    f"{_get_cloud_url()}/{self.teamspace.owner.name}/{self.teamspace.name}/"
                    f"jobs/{mmt_name}?app_id=mmt&machine_name={self.name}"
                )
            return f"{_get_cloud_url()}/{self.teamspace.owner.name}/{self.teamspace.name}/jobs/{self.name}?app_id=jobs"

        # TODO: MMT env with studio
        return super().link

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

    def _update_internal_job(self) -> None:
        if getattr(self, "_job", None) is None:
            self._job = self._job_api.get_job_by_name(name=self._name, teamspace_id=self._teamspace.id)
            return

        self._job = self._job_api.get_job(job_id=self._job.id, teamspace_id=self._teamspace.id)
