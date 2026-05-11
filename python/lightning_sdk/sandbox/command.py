""":class:`Command` handle for sandbox processes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lightning_sdk.api.sandbox_api import CommandStatus

if TYPE_CHECKING:
    from lightning_sdk.sandbox.base import SandboxInstance


class Command:
    """Handle for a command running (or finished) inside a sandbox.

    - When :meth:`SandboxInstance.run_command` is called *without* ``detached=True``,
      the server has already waited for the process to exit, so :attr:`exit_code`
      is an ``int`` and :attr:`running` is ``False`` immediately.
    - When ``detached=True`` is passed, the call returns immediately with
      :attr:`exit_code` set to ``None`` and :attr:`running` set to ``True``.
      Call :meth:`wait` to block until the process exits, or :meth:`kill` to
      terminate it.

    Example::

        detached_cmd = sandbox.run_command(
            RunCommandOpts(cmd="sleep", args=["5"], detached=True)
        )
        result = detached_cmd.wait()
        if result.exit_code != 0:
            print("Something went wrong...")
    """

    def __init__(
        self,
        sandbox: SandboxInstance,
        *,
        cmd_id: str,
        output: str = "",
        exit_code: int | None = None,
    ) -> None:
        self._sandbox = sandbox
        self._cmd_id = cmd_id
        self._output = output
        self._exit_code = exit_code

    @property
    def cmd_id(self) -> str:
        return self._cmd_id

    @property
    def output(self) -> str:
        """Captured combined stdout/stderr seen so far. Updated by :meth:`wait` and :meth:`get_status`."""
        return self._output

    @property
    def exit_code(self) -> int | None:
        """Exit code; ``None`` while the command is still running."""
        return self._exit_code

    @property
    def running(self) -> bool:
        """``True`` while the command is still executing (i.e. :attr:`exit_code` is ``None``)."""
        return self._exit_code is None

    def stdout(self) -> str:
        """Return the captured combined stdout/stderr buffered on the handle."""
        return self._output

    def stderr(self) -> str:
        """Alias for :meth:`stdout`; the API exposes a single combined output stream."""
        return self._output

    def get_status(self) -> CommandStatus:
        """Refresh status from the server, updating :attr:`output` and :attr:`exit_code`.

        Returns the raw :class:`CommandStatus` for inspecting ``running`` directly.
        """
        status = self._sandbox.get_command(self._cmd_id)
        self._output = status.output
        if not status.running:
            self._exit_code = status.exit_code
        return status

    def wait(
        self,
        *,
        timeout: float | None = None,
        poll_interval: float = 0.5,
    ) -> Command:
        """Block until the command exits, then return ``self`` with :attr:`exit_code` populated.

        Essential for detached commands where you need to know when execution
        completes; for non-detached commands, :meth:`SandboxInstance.run_command`
        already waits automatically and ``wait()`` returns immediately.

        Args:
            timeout: Maximum seconds to wait. ``None`` (default) waits indefinitely.
            poll_interval: Seconds between polls.

        Raises:
            TimeoutError: If ``timeout`` elapses before the command exits.
        """
        if self._exit_code is not None:
            return self
        final = self._sandbox.wait_for_command(
            self._cmd_id,
            timeout=timeout,
            poll_interval=poll_interval,
        )
        self._output = final.output
        self._exit_code = final.exit_code
        return self

    def kill(self) -> None:
        """Terminate the command (best effort) via :meth:`SandboxInstance.kill_command`."""
        self._sandbox.kill_command(self._cmd_id)

    def __repr__(self) -> str:
        """Return a string representation for debugging."""
        return f"Command(cmd_id={self._cmd_id!r}, exit_code={self._exit_code!r}, running={self.running})"
