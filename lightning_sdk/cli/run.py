from typing import TYPE_CHECKING, Dict, Optional

from lightning_sdk.job import Job
from lightning_sdk.machine import Machine
from lightning_sdk.mmt import MMT
from lightning_sdk.teamspace import Teamspace

if TYPE_CHECKING:
    from lightning_sdk.cli.legacy import _LegacyLightningCLI

_MACHINE_VALUES = tuple([machine.value for machine in Machine])


class _Run:
    """Run async workloads on the Lightning AI platform."""

    def __init__(self, legacy_run: Optional["_LegacyLightningCLI"] = None) -> None:
        if legacy_run is not None:
            self.app = legacy_run.app
            self.model = legacy_run.model

        # Need to set the docstring here for f-strings to work.
        # Sadly this is the only way to really show options as f-strings are not allowed as docstrings directly
        # and fire does not show values for literals, just that it is a literal.
        docstr_job = f"""Run async workloads using a docker image or a compute environment from your studio.

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
        # TODO: the docstrings from artifacts_local and artifacts_remote don't show up completely,
        # might need to switch to explicit cli definition
        self.job.__func__.__doc__ = docstr_job

        # Need to set the docstring here for f-strings to work.
        # Sadly this is the only way to really show options as f-strings are not allowed as docstrings directly
        # and fire does not show values for literals, just that it is a literal.
        docstr_mmt = f"""Run async workloads on multiple machines using a docker image.

        Args:
            name: The name of the job. Needs to be unique within the teamspace.
            num_machines: The number of Machines to run on. Defaults to 2 Machines
            machine: The machine type to run the job on. One of {", ".join(_MACHINE_VALUES)}. Defaults to CPU
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
        # TODO: the docstrings from artifacts_local and artifacts_remote don't show up completely,
        # might need to switch to explicit cli definition
        self.mmt.__func__.__doc__ = docstr_mmt

    # TODO: sadly, fire displays both Optional[type] and Union[type, None] as Optional[Optional]
    # see https://github.com/google/python-fire/pull/513
    # might need to move to different cli library
    def job(
        self,
        name: str,
        machine: Optional[str] = None,
        command: Optional[str] = None,
        studio: Optional[str] = None,
        image: Optional[str] = None,
        teamspace: Optional[str] = None,
        org: Optional[str] = None,
        user: Optional[str] = None,
        cloud_account: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
        image_credentials: Optional[str] = None,
        cloud_account_auth: bool = False,
        artifacts_local: Optional[str] = None,
        artifacts_remote: Optional[str] = None,
    ) -> None:
        if machine is None:
            # TODO: infer from studio
            machine = "CPU"
        machine_enum = Machine(machine.upper())

        resolved_teamspace = Teamspace(name=teamspace, org=org, user=user)

        if cloud_account is None:
            cloud_account = resolved_teamspace.default_cloud_account
        machine_enum = Machine(machine.upper())
        Job.run(
            name=name,
            machine=machine_enum,
            command=command,
            studio=studio,
            image=image,
            teamspace=resolved_teamspace,
            org=org,
            user=user,
            cloud_account=cloud_account,
            env=env,
            interruptible=interruptible,
            image_credentials=image_credentials,
            cloud_account_auth=cloud_account_auth,
            artifacts_local=artifacts_local,
            artifacts_remote=artifacts_remote,
        )

    # TODO: sadly, fire displays both Optional[type] and Union[type, None] as Optional[Optional]
    # see https://github.com/google/python-fire/pull/513
    # might need to move to different cli library
    def mmt(
        self,
        name: Optional[str] = None,
        num_machines: int = 2,
        machine: Optional[str] = None,
        command: Optional[str] = None,
        image: Optional[str] = None,
        teamspace: Optional[str] = None,
        org: Optional[str] = None,
        user: Optional[str] = None,
        cloud_account: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
        image_credentials: Optional[str] = None,
        cloud_account_auth: bool = False,
        artifacts_local: Optional[str] = None,
        artifacts_remote: Optional[str] = None,
    ) -> None:
        if name is None:
            from datetime import datetime

            timestr = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            name = f"mmt-{timestr}"

        if machine is None:
            # TODO: infer from studio
            machine = "CPU"
        machine_enum = Machine(machine.upper())

        resolved_teamspace = Teamspace(name=teamspace, org=org, user=user)
        if cloud_account is None:
            cloud_account = resolved_teamspace.default_cloud_account

        if image is None:
            raise RuntimeError("Image needs to be specified to run a multi-machine job")

        MMT.run(
            name=name,
            num_machines=num_machines,
            machine=machine_enum,
            command=command,
            studio=None,
            image=image,
            teamspace=resolved_teamspace,
            org=org,
            user=user,
            cloud_account=cloud_account,
            env=env,
            interruptible=interruptible,
            image_credentials=image_credentials,
            cloud_account_auth=cloud_account_auth,
            artifacts_local=artifacts_local,
            artifacts_remote=artifacts_remote,
        )
