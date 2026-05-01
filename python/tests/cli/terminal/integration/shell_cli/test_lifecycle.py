"""Shell script tests for full session lifecycle: new, ls, send, read, status, kill."""

from __future__ import annotations

from cli.terminal.integration.conftest import terminal_integration


@terminal_integration
class TestScriptLifecycle:
    """lightningterminal.sh — full lifecycle through the shell script."""

    def test_lifecycle(self, shell_env):
        """Full script lifecycle: new -> ls -> send -> read -> status -> kill -> ls."""
        result = shell_env.run("new", "--name", "lifecycle-test")
        session_id = ""
        for line in result.stdout.splitlines():
            if line.startswith("session_id: "):
                session_id = line.partition(": ")[2]
                break

        shell_env.run("ls")

        shell_env.run("send", "--id", session_id, "echo LIFECYCLE_MARKER", wait_for_completion=True)

        shell_env.run("read", "--id", session_id)
        shell_env.run("status", "--id", session_id)
        shell_env.run("kill", "--id", session_id)
        shell_env.run("ls")
