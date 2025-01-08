from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Union

from lightning_sdk.api.mmt_api import MMTApiV2

if TYPE_CHECKING:
    from lightning_sdk.job.job import Job
    from lightning_sdk.machine import Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.status import Status
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
            artifacts_local=artifacts_local,
            artifacts_remote=artifacts_remote,
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
    def _latest_job(self) -> Any:
        """Guarantees to fetch the latest version of a job before returning it."""
        self._update_internal_job()
        return self._job

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
    def machine(self) -> "Machine":
        """Returns the machine type this job is running on."""
        return self._job_api._get_job_machine_from_spec(self._guaranteed_job.spec)

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
        # TODO: Since we don't have a UI for this yet, we can't have a link
        raise NotImplementedError
