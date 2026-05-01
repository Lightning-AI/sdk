"""Shell script tests for lightningterminal.sh send and read."""

from __future__ import annotations

from cli.terminal.integration.conftest import terminal_integration


@terminal_integration
class TestScriptSend:
    """lightningterminal.sh send — send commands to sessions."""

    def test_send_requires_id(self, shell_env):
        """Sending without --id or --name gives a clear error."""
        result = shell_env.run_expect_error("send", "echo hello")
        assert "--id or --name is required" in result.stderr

    def test_send_command(self, shell_env):
        """Sending a command to a session succeeds (silent on success)."""
        session = shell_env.given_session(name="Worker")
        shell_env.run("send", "--id", session.id, "echo SEND_TEST_MARKER")

    def test_send_by_name(self, shell_env):
        """Send accepts --name to find a session by terminal name."""
        shell_env.given_session(name="Worker")
        shell_env.run("send", "--name", "Worker", "echo NAME_MARKER", wait_for_completion=True)
        result = shell_env.run("read", "--name", "Worker")
        assert "NAME_MARKER" in result.stdout

    def test_send_to_nonexistent_session(self, shell_env):
        """Sending to a nonexistent session gives a clear error."""
        result = shell_env.run_expect_error("send", "--id", "nonexistent-id", "echo hello")
        assert "no terminal session found" in result.stderr


@terminal_integration
class TestScriptRead:
    """lightningterminal.sh read — read session buffer."""

    def test_read_requires_id(self, shell_env):
        """Reading without --id or --name gives a clear error."""
        result = shell_env.run_expect_error("read")
        assert "--id or --name is required" in result.stderr

    def test_read_nonexistent_session(self, shell_env):
        """Reading a nonexistent session gives a clear error."""
        result = shell_env.run_expect_error("read", "--id", "nonexistent-id")
        assert "no terminal session found" in result.stderr

    def test_read_after_send(self, shell_env):
        """Reading a session buffer shows previously sent command output."""
        session = shell_env.given_session(name="Worker")

        shell_env.run("send", "--id", session.id, "echo READ_TEST_MARKER_42", wait_for_completion=True)

        result = shell_env.run("read", "--id", session.id)
        assert "READ_TEST_MARKER_42" in result.stdout

    def test_read_empty_session(self, shell_env):
        """Reading a fresh session succeeds."""
        session = shell_env.given_session(name="Fresh")
        shell_env.run("read", "--id", session.id)

    def test_read_multiple_commands(self, shell_env):
        """Multiple sent commands all appear in the buffer."""
        session = shell_env.given_session(name="Multi")

        shell_env.run("send", "--id", session.id, "echo FIRST_MARKER")
        shell_env.run("send", "--id", session.id, "echo SECOND_MARKER", wait_for_completion=True)

        result = shell_env.run("read", "--id", session.id)
        assert "FIRST_MARKER" in result.stdout
        assert "SECOND_MARKER" in result.stdout

    def test_send_to_attached_session(self, shell_env):
        """Send works even when a PTY is attached to the session."""
        session = shell_env.given_session(name="Attached")
        shell_env.attach_session(session.id)

        shell_env.run("send", "--id", session.id, "echo ATTACHED_MARKER", wait_for_completion=True)
        result = shell_env.run("read", "--id", session.id)
        assert "ATTACHED_MARKER" in result.stdout

    def test_send_with_pipe(self, shell_env):
        """Commands containing pipes are handled correctly."""
        session = shell_env.given_session(name="Pipes")
        shell_env.run("send", "--id", session.id, "echo PIPE_INPUT | cat", wait_for_completion=True)
        result = shell_env.run("read", "--id", session.id)
        assert "PIPE_INPUT" in result.stdout
