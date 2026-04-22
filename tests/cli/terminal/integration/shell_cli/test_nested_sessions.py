"""Shell script tests for creating sessions inside existing sessions.

Verifies that env vars (LIGHTNING_TERMINAL_SESSION_ID, etc.) don't leak
from the parent script process into child sessions, and that attaching
to a session from inside another session works correctly.
"""

from __future__ import annotations

from cli.terminal.integration.conftest import terminal_integration


@terminal_integration
class TestNestedSessions:
    """Creating a session from inside another session doesn't leak env vars."""

    def test_second_session_has_own_identity(self, shell_env):
        """Each session gets its own LIGHTNING_TERMINAL_SESSION_ID."""
        first = shell_env.given_session(name="First")
        second = shell_env.given_session(name="Second")
        assert first.id != second.id

        shell_env.run("ls")

        result_first = shell_env.run("status", "--id", first.id)
        assert "First" in result_first.stdout

        result_second = shell_env.run("status", "--id", second.id)
        assert "Second" in result_second.stdout


@terminal_integration
class TestAttachFromInsideSession:
    """Attaching to a session from inside another session (the production use case).

    In studios, the user is always inside a screen session. When they
    switch terminals, the outer session attaches to the inner session
    via `lightningterminal.sh attach`. The outer session should be
    marked as delegated while the inner session is displayed.
    """

    def test_attach_inner_from_outer(self, shell_env):
        """Attach to inner session from inside outer session via PTY.

        Verifies the inner session's prompt is visible through the
        outer session's PTY after the attach command.
        """
        outer = shell_env.given_session(name="Outer")
        inner = shell_env.given_session(name="Inner")

        handle = shell_env.attach_session(outer.id)
        handle.wait_for("$")

        # From inside outer, attach to inner
        handle.send_line(f"lt attach --id {inner.id}")
        # We should see the inner session's prompt
        handle.wait_for("$")

        # Type something in the inner session to verify we're in it
        handle.send_line("echo INNER_MARKER")
        handle.wait_for("INNER_MARKER")

    def test_delegation_metadata(self, shell_env):
        """Outer session shows delegated_to while inner is attached."""
        outer = shell_env.given_session(name="Outer")
        inner = shell_env.given_session(name="Inner")

        handle = shell_env.attach_session(outer.id)
        handle.wait_for("$")

        # Attach to inner from inside outer
        handle.send_line(f"lt attach --id {inner.id}")
        handle.wait_for("$")

        # Delegation should appear in raw output
        shell_env.wait_until(
            lambda: "delegated_to:" in shell_env.run("status", "--id", outer.id, "--raw").stdout,
            message="Outer session should show delegated_to metadata",
        )
        result = shell_env.run("status", "--id", outer.id, "--raw")
        assert f"delegated_to: {inner.id}" in result.stdout
