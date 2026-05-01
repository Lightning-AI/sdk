"""Shell script tests for lt help."""

from __future__ import annotations

from cli.terminal.integration.conftest import terminal_integration


@terminal_integration
class TestLtHelp:
    """The `lt help` command shows usage."""

    def test_lt_help(self, shell_env):
        """lt help shows usage with 'lt' as the script name."""
        session = shell_env.given_session(name="Helper")
        handle = shell_env.attach_session(session.id)
        handle.wait_for("$")

        handle.send_line("lt help")
        handle.wait_for("Usage: lt")
        handle.snapshot("lt help output")

    def test_lt_dash_dash_help(self, shell_env):
        """lt --help also shows usage."""
        session = shell_env.given_session(name="DashHelper")
        handle = shell_env.attach_session(session.id)
        handle.wait_for("$")

        handle.send_line("lt --help")
        handle.wait_for("Usage: lt")
        handle.snapshot("lt --help output")
