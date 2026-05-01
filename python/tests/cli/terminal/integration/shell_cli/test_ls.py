"""Shell script tests for lightningterminal.sh ls."""

from __future__ import annotations

from cli.terminal.integration.conftest import terminal_integration


@terminal_integration
class TestScriptLs:
    """lightningterminal.sh ls — listing sessions via the shell script."""

    def test_empty(self, shell_env):
        """ls with no sessions returns empty output."""
        shell_env.run("ls")

    def test_single_named_session(self, shell_env):
        """ls output for a single named session."""
        shell_env.given_session(name="Backend")
        shell_env.run("ls")

    def test_single_anonymous_session(self, shell_env):
        """ls output for an anonymous session."""
        shell_env.given_session()
        shell_env.run("ls")


@terminal_integration
class TestScriptLsFormat:
    """lightningterminal.sh ls — one-liner format assertions."""

    def test_oneliner_contains_name_status_id(self, shell_env):
        """Default ls output contains name, status, and id in one line."""
        session = shell_env.given_session(name="Backend")
        result = shell_env.run("ls")
        line = result.stdout.strip()
        assert line.startswith("Backend")
        assert "detached" in line
        assert f"id={session.id}" in line

    def test_oneliner_shows_last_command(self, shell_env):
        """One-liner includes last_command after a command is sent."""
        session = shell_env.given_session(name="Worker")
        shell_env.run("send", "--id", session.id, "echo hello", wait_for_completion=True)
        result = shell_env.run("ls")
        line = result.stdout.strip()
        assert "Worker - echo" in line

    def test_oneliner_vs_raw(self, shell_env):
        """Default and --raw produce different formats for the same session."""
        shell_env.given_session(name="Backend")
        oneliner = shell_env.run("ls")
        raw = shell_env.run("ls", "--raw")
        # One-liner is a single line with parenthesised status
        assert "(" in oneliner.stdout
        assert "session_id:" not in oneliner.stdout
        # Raw is multi-line key-value
        assert "session_id:" in raw.stdout
        assert "terminal_name: Backend" in raw.stdout

    def test_multiple_sessions(self, shell_env):
        """ls shows all sessions."""
        shell_env.given_session(name="Alpha")
        shell_env.given_session(name="Beta")
        result = shell_env.run("ls")
        assert "Alpha" in result.stdout
        assert "Beta" in result.stdout


@terminal_integration
class TestScriptLsRaw:
    """lightningterminal.sh ls --raw — key-value output for scripts."""

    def test_raw_output_fields(self, shell_env):
        """Raw ls output contains all expected fields per record."""
        shell_env.given_session(name="Backend")
        result = shell_env.run("ls", "--raw")
        for field in (
            "session_id:",
            "pid:",
            "status:",
            "terminal_name:",
            "default_name:",
            "display_label:",
            "last_command:",
            "created:",
        ):
            assert field in result.stdout

    def test_raw_multiple_sessions(self, shell_env):
        """Raw ls shows all sessions with session_id fields."""
        shell_env.given_session(name="Alpha")
        shell_env.given_session(name="Beta")
        result = shell_env.run("ls", "--raw")
        assert result.stdout.count("session_id:") == 2
        assert "terminal_name: Alpha" in result.stdout
        assert "terminal_name: Beta" in result.stdout


@terminal_integration
class TestScriptLsOrdering:
    """lightningterminal.sh ls — output ordering by creation date."""

    def test_creation_order(self, shell_env):
        """Sessions appear in creation order (oldest first)."""
        shell_env.given_session(name="First")
        shell_env.given_session(name="Second")
        shell_env.given_session(name="Third")

        result = shell_env.run("ls")
        lines = result.stdout.strip().splitlines()
        assert lines[0].startswith("First")
        assert lines[1].startswith("Second")
        assert lines[2].startswith("Third")

    def test_attached_still_in_creation_order(self, shell_env):
        """Attached sessions don't change script-level ordering (sorted by created)."""
        shell_env.given_session(name="Detached")
        shell_env.given_session(name="Attached", attached=True)

        result = shell_env.run("ls")
        lines = result.stdout.strip().splitlines()
        assert lines[0].startswith("Detached")
        assert lines[1].startswith("Attached")


@terminal_integration
class TestLtLs:
    """The `lt ls` convenience function."""

    def test_lt_ls(self, shell_env):
        """lt ls works as a shorthand for lightningterminal.sh ls."""
        session = shell_env.given_session(name="ListMe")
        handle = shell_env.attach_session(session.id)
        handle.wait_for("$")

        handle.send_line("lt ls")
        handle.wait_for("ListMe")
        handle.snapshot("lt ls output")
