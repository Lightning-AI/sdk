import ast
import types
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Type, Union

from lightning_sdk.machine import CloudProvider, Machine
from lightning_sdk.organization import Organization
from lightning_sdk.status import Status
from lightning_sdk.studio import Studio
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User


@dataclass
class Output:
    text: str
    exit_code: int


class _Sandbox:
    """Sandbox runs AI generated code safely and discards the machine after use.

    Users can run any arbitrary code in a sandbox with sudo permissions.

    Args:
        name: The name of the sandbox.
        machine: The machine to use for the sandbox.
        interruptible: Whether the sandbox is interruptible.
        teamspace: The teamspace to use for the sandbox.
        org: The organization to use for the sandbox.
        user: The user to use for the sandbox.
        cloud_account: The cloud account to use for the sandbox.
        cloud_provider: Selects the cloud account based on the available cloud accounts and the specified provider.
        disable_secrets: If true, user secrets such as LIGHTNING_API_KEY are not stored in the sandbox.

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
        cloud_provider: Optional[Union[CloudProvider, str]] = None,
        disable_secrets: bool = True,
    ) -> None:
        if name is None:
            timestr = datetime.now().strftime("%b-%d-%H_%M")
            name = f"sandbox-{timestr}"

        self._machine = machine or Machine.CPU
        self._interruptible = interruptible
        self._studio = Studio(
            name=name,
            teamspace=teamspace,
            org=org,
            user=user,
            cloud_account=cloud_account,
            cloud_provider=cloud_provider,
            disable_secrets=disable_secrets,
        )

    @property
    def is_running(self) -> bool:
        return self._studio.status == Status.Running

    def start(self) -> None:
        """Starts the sandbox if it is not already running."""
        if self._studio.status == Status.Running:
            raise RuntimeError(
                "Cannot start sandbox: it is already running.\n\n"
                "To ensure proper lifecycle management, either:\n"
                "  • Avoid calling `start()` multiple times manually, or\n"
                "  • Use the sandbox as a context manager:\n"
                "      with Sandbox() as sandbox:\n"
                "          # your code here\n"
            )

        if self._studio.status == Status.Pending:
            raise RuntimeError("Cannot start sandbox: it is already starting. Wait for it to finish starting.")
        self._studio.start(machine=self._machine, interruptible=self._interruptible)

    def delete(self) -> None:
        """Deletes the sandbox if it is not already deleted."""
        if self._studio.status == Status.NotCreated:
            raise RuntimeError("Cannot delete sandbox: it is not created.")
        self._studio.delete()

    def run(self, command: str) -> Output:
        """Runs the command and returns the output."""
        output, exit_code = self._studio.run_with_exit_code(command)
        if exit_code != 0:
            raise Exception(f"Command failed with exit code {exit_code}: {output}")
        return Output(text=output, exit_code=exit_code)

    @staticmethod
    def _validate_python_code(code: str) -> None:
        """Validates Python code for syntax errors.

        Args:
            code: The Python code string to validate

        Raises:
            SyntaxError: If the code has syntax errors
            ValueError: If the code is empty or only whitespace
            IndentationError: If the code has improper indentation

        Note:
            This validation only catches syntax-level errors. Runtime errors like
            NameError or TypeError can only be caught when the code is actually executed.
        """
        if not code or not code.strip():
            raise ValueError("Code cannot be empty or only whitespace")

        try:
            ast.parse(code)
        except (SyntaxError, IndentationError) as e:
            error_type = type(e).__name__
            raise type(e)(f"Invalid Python {error_type.lower()}: {e}") from e

    def run_python_code(self, code: str) -> Output:
        """Runs the python code and returns the output.

        Args:
            code: The Python code string to execute

        Returns:
            Output: The result of executing the code

        Raises:
            SyntaxError: If the code has syntax errors
            ValueError: If the code is empty or only whitespace
        """
        # Validate the code before running
        self._validate_python_code(code)

        command = f"python - <<EOF\n{code}\nEOF"
        return self.run(command)

    def __enter__(self) -> "_Sandbox":
        """Starts the sandbox if it is not running and returns the sandbox."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]] = None,
        exc_value: Optional[BaseException] = None,
        traceback: Optional[types.TracebackType] = None,
    ) -> None:
        """Deletes the sandbox after use."""
        self._studio.delete()
