""":class:`Command` handle for sandbox processes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lightning_sdk.api.sandbox_api import CommandLog, CommandStatus

if TYPE_CHECKING:
    from datetime import datetime

    from lightning_sdk.lightning_cloud.openapi.models import V1SandboxCommand
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

    :attr:`started_at` (the server-side start time, the model's ``created_at``)
    and :attr:`updated_at` (last server update) are only populated on handles from
    :meth:`SandboxInstance.list_commands`. They are ``None`` on handles from
    :meth:`run_command` and :meth:`SandboxInstance.get_command`, whose endpoints do
    not return timestamps.

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
        command: str | None = None,
        output: str = "",
        exit_code: int | None = None,
        started_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self._sandbox = sandbox
        self._cmd_id = cmd_id
        self._command = command
        self._output = output
        self._exit_code = exit_code
        self._started_at = started_at
        self._updated_at = updated_at

    @classmethod
    def _from_v1(cls, sandbox: SandboxInstance, v1: V1SandboxCommand) -> Command:
        """Build a handle from a raw ``V1SandboxCommand`` row (list/get endpoints)."""
        running = bool(v1.running)
        return cls(
            sandbox,
            cmd_id=v1.id or "",
            command=v1.command or None,
            output=v1.output or "",
            exit_code=None if running else int(v1.exit_code or 0),
            started_at=v1.created_at,
            updated_at=v1.updated_at,
        )

    @property
    def id(self) -> str:
        """Server-assigned command identifier (alias of :attr:`cmd_id`)."""
        return self._cmd_id

    @property
    def cmd_id(self) -> str:
        return self._cmd_id

    @property
    def command(self) -> str | None:
        """The command string that was launched, when known."""
        return self._command

    @property
    def started_at(self) -> datetime | None:
        """Server-side start time (model ``created_at``), or ``None`` when unavailable."""
        return self._started_at

    @property
    def updated_at(self) -> datetime | None:
        """Last server-side update time, or ``None`` when unavailable.

        For a finished command this is effectively when it stopped; while running
        it tracks the most recent output/status update.
        """
        return self._updated_at

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

    def logs(self) -> list[CommandLog]:
        """Fetch this command's log lines from the server.

        Returns the timestamped log messages via
        :meth:`SandboxInstance.get_command_logs`. Unlike :meth:`output` (a single
        combined buffer), this returns discrete ``(timestamp, message)`` entries.
        """
        return self._sandbox.get_command_logs(self._cmd_id)

    def get_status(self) -> CommandStatus:
        """Refresh status from the server, updating :attr:`output` and :attr:`exit_code`.

        Returns the raw :class:`CommandStatus` for inspecting ``running`` directly.
        """
        status = self._sandbox._get_command_status(self._cmd_id)
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
