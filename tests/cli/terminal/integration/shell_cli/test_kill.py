"""Shell script tests for lightningterminal.sh kill."""

from __future__ import annotations

from cli.terminal.integration.conftest import terminal_integration


@terminal_integration
class TestScriptKill:
    """lightningterminal.sh kill — kill sessions."""

    def test_kill_and_verify(self, shell_env):
        """Killing a session removes it from ls."""
        session = shell_env.given_session(name="Doomed")
        result = shell_env.run("ls")
        assert "Doomed" in result.stdout

        shell_env.run("kill", "--id", session.id)

        result = shell_env.run("ls")
        assert "Doomed" not in result.stdout

    def test_kill_cleans_metadata(self, shell_env):
        """Killing a session removes its metadata — status errors."""
        session = shell_env.given_session(name="Cleanup")
        result = shell_env.run("status", "--id", session.id)
        assert "Cleanup" in result.stdout

        shell_env.run("kill", "--id", session.id)

        result = shell_env.run_expect_error("status", "--id", session.id)
        assert "no terminal session found" in result.stderr

    def test_kill_by_name(self, shell_env):
        """Kill accepts --name to find a session by terminal name."""
        shell_env.given_session(name="Doomed")
        shell_env.run("kill", "--name", "Doomed")
        result = shell_env.run("ls")
        assert "Doomed" not in result.stdout

    def test_kill_positional_arg_rejected(self, shell_env):
        """Passing a name without --name is rejected, not silently ignored.

        Previously, `lt kill my-session` would ignore the positional arg
        and kill the current session instead.
        """
        session = shell_env.given_session(name="DontKillMe")
        shell_env.set_env("LIGHTNING_TERMINAL_SESSION_ID", session.id)

        result = shell_env.run_expect_error("kill", "DontKillMe")
        assert "unexpected argument" in result.stderr

        # Session should still be alive
        result = shell_env.run("ls")
        assert "DontKillMe" in result.stdout

    def test_kill_nonexistent_session(self, shell_env):
        """Killing a nonexistent session gives a clear error."""
        result = shell_env.run_expect_error("kill", "--id", "nonexistent-id")
        assert "no terminal session found" in result.stderr

    def test_kill_attached_session(self, shell_env):
        """Killing a session that has a PTY attached still works.

        The PTY snapshot shows "[screen is terminating]" — this is
        hardcoded in GNU screen's source and can't be customised.
        """
        session = shell_env.given_session(name="Attached")
        shell_env.attach_session(session.id)

        shell_env.run("kill", "--id", session.id)

        result = shell_env.run("ls")
        assert "Attached" not in result.stdout

    def test_two_clients_one_exits(self, shell_env):
        """Two PTYs attached to the same session. One types exit.

        Both clients see the same session. When client B exits the
        shell, screen terminates and both PTYs disconnect.
        """
        session = shell_env.given_session(name="Shared")

        client_a = shell_env.attach_session(session.id)
        client_b = shell_env.attach_session(session.id)
        client_a.wait_for("$")

        client_a.send_line("echo FROM_CLIENT_A")
        client_a.wait_for("FROM_CLIENT_A")
        client_b.wait_for("FROM_CLIENT_A")
        client_b.snapshot("B sees A's echo")

        client_b.send_line("exit")

    def test_kill_current_session(self, shell_env):
        """Kill defaults to the current session when --id is omitted.

        Uses a PTY so the command genuinely runs inside a session
        with LIGHTNING_TERMINAL_SESSION_ID set.
        """
        session = shell_env.given_session(name="Doomed")
        handle = shell_env.attach_session(session.id)
        handle.wait_for("$")

        handle.send_line("lt kill")

        shell_env.wait_until(
            lambda: "Doomed" not in shell_env.run("ls").stdout,
            message="Session should be killed",
        )

    def test_kill_no_session_errors(self, shell_env):
        """Kill without --id and outside a session gives a clear error."""
        result = shell_env.run_expect_error("kill")
        assert "--id is required" in result.stderr

    def test_kill_one_of_multiple(self, shell_env):
        """Killing one session doesn't affect others."""
        shell_env.given_session(name="Survivor")
        s2 = shell_env.given_session(name="Victim")

        shell_env.run("kill", "--id", s2.id)

        result = shell_env.run("ls")
        assert "Survivor" in result.stdout
        assert "Victim" not in result.stdout
