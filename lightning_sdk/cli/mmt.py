from typing import Dict, Optional

from fire import Fire

from lightning_sdk._mmt import MMT
from lightning_sdk.api.studio_api import _cloud_url
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.machine import Machine
from lightning_sdk.teamspace import Teamspace

_MACHINE_VALUES = tuple([machine.value for machine in Machine])


class MMTCLI:
    """Command line interface (CLI) to interact with/manage Lightning AI MMT."""

    def __init__(self) -> None:
        # Need to set the docstring here for f-strings to work.
        # Sadly this is the only way to really show options as f-strings are not allowed as docstrings directly
        # and fire does not show values for literals, just that it is a literal.
        docstr = f"""Run async workloads on multiple machines using a docker image.

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
        self.run.__func__.__doc__ = docstr

    def login(self) -> None:
        """Login to Lightning AI Studios."""
        auth = Auth()
        auth.clear()

        try:
            auth.authenticate()
        except ConnectionError:
            raise RuntimeError(f"Unable to connect to {_cloud_url()}. Please check your internet connection.") from None

    def logout(self) -> None:
        """Logout from Lightning AI Studios."""
        auth = Auth()
        auth.clear()

    # TODO: sadly, fire displays both Optional[type] and Union[type, None] as Optional[Optional]
    # see https://github.com/google/python-fire/pull/513
    # might need to move to different cli library
    def run(
        self,
        name: Optional[str] = None,
        num_machines: int = 2,
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
        if name is None:
            from datetime import datetime

            timestr = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            name = f"mmt-{timestr}"

        if machine is None:
            # TODO: infer from studio
            machine = "CPU"
        machine_enum = Machine(machine.upper())

        teamspace = Teamspace(name=teamspace, org=org, user=user)
        if cloud_account is None:
            cloud_account = teamspace.default_cloud_account

        if image is None:
            raise RuntimeError("Currently only docker images are specified")
        MMT.run(
            name=name,
            num_machines=num_machines,
            machine=machine_enum,
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
        )


def main_cli() -> None:
    """CLI entrypoint."""
    Fire(MMTCLI(), name="_mmt")


if __name__ == "__main__":
    main_cli()
