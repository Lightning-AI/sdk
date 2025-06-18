import types
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Type, Union

from lightning_sdk.machine import Machine
from lightning_sdk.organization import Organization
from lightning_sdk.status import Status
from lightning_sdk.studio import Studio
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User


@dataclass
class Output:
    text: str
    exit_code: int


class Sandbox:
    """Sandbox runs AI generated code safely and discards the machine after use.

    Example:
        with Sandbox() as sandbox:
            output = sandbox.run("python --version")
            print(output.text)
    """

    def __init__(
        self,
        name: Optional[str] = None,
        machine: Optional[str] = None,
        interruptible: Optional[bool] = None,
        teamspace: Optional[Union[str, Teamspace]] = None,
        org: Optional[Union[str, Organization]] = None,
        user: Optional[Union[str, User]] = None,
        cloud_account: Optional[str] = None,
    ) -> None:
        if name is None:
            timestr = datetime.now().strftime("%b-%d-%H_%M")
            name = f"sandbox-{timestr}"

        self._machine = machine or Machine.CPU
        self._interruptible = interruptible
        self._studio = Studio(name=name, teamspace=teamspace, org=org, user=user, cloud_account=cloud_account)

    @property
    def is_running(self) -> bool:
        return self._studio.status == Status.Running

    def run(self, command: str) -> Output:
        """Runs the command and returns the output."""
        output, exit_code = self._studio.run_with_exit_code(command)
        if exit_code != 0:
            raise Exception(f"Command failed with exit code {exit_code}: {output}")
        return Output(text=output, exit_code=exit_code)

    def __enter__(self) -> "Sandbox":
        """Starts the sandbox if it is not running and returns the sandbox."""
        if not self.is_running:
            self._studio.start(machine=self._machine, interruptible=self._interruptible)
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]] = None,
        exc_value: Optional[BaseException] = None,
        traceback: Optional[types.TracebackType] = None,
    ) -> None:
        """Deletes the sandbox after use."""
        self._studio.delete()
