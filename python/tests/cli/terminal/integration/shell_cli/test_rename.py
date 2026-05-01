"""Shell script tests for lightningterminal.sh rename."""

from __future__ import annotations

from cli.terminal.integration.conftest import terminal_integration


@terminal_integration
class TestScriptRename:
    """lightningterminal.sh rename — rename sessions."""

    def test_rename_with_explicit_id(self, shell_env):
        """Rename a session by providing --id."""
        session = shell_env.given_session(name="OldName")
        result = shell_env.run("status", "--id", session.id)
        assert "OldName" in result.stdout

        shell_env.run("rename", "--id", session.id, "NewName")

        result = shell_env.run("status", "--id", session.id)
        assert "NewName" in result.stdout

    def test_rename_by_name(self, shell_env):
        """Rename accepts --name to find a session by terminal name."""
        shell_env.given_session(name="OldName")
        shell_env.run("rename", "--name", "OldName", "NewName")

        result = shell_env.run("ls")
        assert "NewName" in result.stdout
        assert "OldName" not in result.stdout

    def test_rename_current_session(self, shell_env):
        """Rename defaults to the current session when --id is omitted.

        Uses a PTY so the command genuinely runs inside a session
        with LIGHTNING_TERMINAL_SESSION_ID set.
        """
        session = shell_env.given_session(name="OldCurrent")
        handle = shell_env.attach_session(session.id)
        handle.wait_for("$")

        handle.send_line("lt rename CurrentName")
        handle.wait_for("$")

        result = shell_env.run("status", "--id", session.id)
        assert "CurrentName" in result.stdout

    def test_rename_no_session_errors(self, shell_env):
        """Rename without --id and outside a session gives a clear error."""
        result = shell_env.run_expect_error("rename", "SomeName")
        assert "--id is required" in result.stderr

    def test_rename_nonexistent_session(self, shell_env):
        """Rename of a nonexistent session gives a clear error."""
        result = shell_env.run_expect_error("rename", "--id", "nonexistent-id", "NewName")
        assert "no terminal session found" in result.stderr

    def test_rename_no_name_errors(self, shell_env):
        """Rename without a new name gives a clear error."""
        session = shell_env.given_session(name="Existing")
        result = shell_env.run_expect_error("rename", "--id", session.id)
        assert "new name is required" in result.stderr

    def test_rename_anonymous_session(self, shell_env):
        """Renaming an anonymous session (no prior name) works."""
        session = shell_env.given_session()
        shell_env.run("rename", "--id", session.id, "GotAName")

        result = shell_env.run("status", "--id", session.id)
        assert "GotAName" in result.stdout

    def test_rename_shows_in_ls(self, shell_env):
        """After rename, ls output reflects the new name."""
        session = shell_env.given_session(name="Before")
        shell_env.run("rename", "--id", session.id, "After")

        result = shell_env.run("ls")
        assert "After" in result.stdout
        assert "Before" not in result.stdout
