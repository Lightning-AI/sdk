"""Shell script tests for detaching from exec'd sessions.

When a session is entered via `exec lightningterminal.sh init`, the
shell process was replaced by screen. Detaching disconnects the client
but the session survives in the background (status: detached). The
terminal/PTY exits because there's no parent shell to return to.
"""

from __future__ import annotations

from cli.terminal.integration.conftest import terminal_integration


@terminal_integration
class TestDetachFromExecSession:
    def test_session_survives_detach(self, shell_env):
        """Detaching from an exec'd session leaves it running (detached).

        The PTY shows '[detached from ...]' and the session remains
        in ls with status: detached — it can be re-attached later.
        """
        handle = shell_env.init_session("exec-test")
        handle.wait_for("$")

        handle.send_line("lt detach")

        shell_env.wait_until(
            lambda: "detached" in shell_env.run("status", "--id", "exec-test").stdout,
            message="Session should be detached but still alive",
        )
