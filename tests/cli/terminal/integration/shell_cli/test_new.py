"""Shell script tests for lightningterminal.sh new — session creation and validation."""

from __future__ import annotations

from cli.terminal.integration.conftest import terminal_integration


@terminal_integration
class TestScriptNew:
    """lightningterminal.sh new — session creation, validation, and edge cases."""

    def test_named_session(self, shell_env):
        """Creating a named session outputs its record."""
        shell_env.run("new", "--name", "Backend")

    def test_anonymous_session(self, shell_env):
        """Creating with no args gives an anonymous session."""
        shell_env.run("new")

    def test_explicit_session_id(self, shell_env):
        """Creating with an explicit --id."""
        shell_env.run("new", "--id", "my-valid_id-123")

    def test_named_with_explicit_id(self, shell_env):
        """Creating with both --name and --id."""
        shell_env.run("new", "--id", "custom-id", "--name", "My Service")

    def test_name_sanitised_in_session_id(self, shell_env):
        """Terminal names with special chars produce sanitised session_ids."""
        shell_env.run("new", "--name", "My Service!!!")

    def test_duplicate_session_id_rejected(self, shell_env):
        """Creating a session with an existing session_id should error."""
        result = shell_env.run("new", "--name", "first")
        session_id = ""
        for line in result.stdout.splitlines():
            if line.startswith("session_id: "):
                session_id = line.partition(": ")[2]
                break
        assert session_id
        shell_env.run_expect_error("new", "--id", session_id)

    def test_invalid_session_id_rejected(self, shell_env):
        """Session IDs with special characters should be rejected."""
        shell_env.run_expect_error("new", "--id", "bad session id!")

    def test_spaces_in_session_id_rejected(self, shell_env):
        shell_env.run_expect_error("new", "--id", "has spaces")


@terminal_integration
class TestScriptNewSource:
    """lightningterminal.sh new --source — session source tagging."""

    def test_source_appears_in_raw_ls(self, shell_env):
        """Source tag appears in ls --raw output."""
        shell_env.run("new", "--name", "AgentTask", "--source", "agent")
        result = shell_env.run("ls", "--raw")
        assert "source: agent" in result.stdout

    def test_source_platform(self, shell_env):
        """Platform source tag is written to metadata."""
        shell_env.run("new", "--name", "Studio", "--source", "platform")
        result = shell_env.run("ls", "--raw")
        assert "source: platform" in result.stdout

    def test_source_without_name(self, shell_env):
        """Source can be set on anonymous sessions."""
        shell_env.run("new", "--source", "application")
        result = shell_env.run("ls", "--raw")
        assert "source: application" in result.stdout

    def test_no_source(self, shell_env):
        """Sessions without --source have no source field in metadata."""
        shell_env.run("new", "--name", "Plain")
        result = shell_env.run("ls", "--raw")
        assert "source:" not in result.stdout

    def test_invalid_source_rejected(self, shell_env):
        """Invalid source values are rejected."""
        result = shell_env.run_expect_error("new", "--name", "Bad", "--source", "unknown")
        assert "--source must be one of" in result.stderr
