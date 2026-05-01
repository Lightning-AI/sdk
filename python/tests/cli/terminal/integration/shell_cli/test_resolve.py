"""Shell script tests for lightningterminal.sh resolve."""

from __future__ import annotations

from cli.terminal.integration.conftest import terminal_integration


@terminal_integration
class TestScriptResolve:
    """lightningterminal.sh resolve — resolve targets to session_ids."""

    def test_resolve_not_found(self, shell_env):
        """Resolving a nonexistent target errors."""
        shell_env.run_expect_error("resolve", "nonexistent")


@terminal_integration
class TestScriptResolveFields:
    """Resolve assertions that depend on dynamic values (PIDs, session_ids)."""

    def test_resolve_by_terminal_name(self, shell_env):
        """Resolving by terminal_name returns the session_id."""
        session = shell_env.given_session(name="Backend")
        result = shell_env.run("resolve", "--by", "terminal_name", "Backend")
        assert result.stdout.strip() == session.id

    def test_resolve_by_session_id(self, shell_env):
        """Resolving by session_id returns itself."""
        session = shell_env.given_session(name="Backend")
        result = shell_env.run("resolve", "--by", "session_id", session.id)
        assert result.stdout.strip() == session.id

    def test_resolve_by_pid(self, shell_env):
        """Resolving by PID returns the session_id."""
        session = shell_env.given_session(name="Backend")
        ls = shell_env.run("ls", "--raw")
        pid = _extract_field(ls.stdout, "pid")
        result = shell_env.run("resolve", "--by", "pid", pid)
        assert result.stdout.strip() == session.id

    def test_resolve_by_default_name(self, shell_env):
        """Resolving by default_name (term-<pid>) returns the session_id."""
        session = shell_env.given_session()
        ls = shell_env.run("ls", "--raw")
        default_name = _extract_field(ls.stdout, "default_name")
        result = shell_env.run("resolve", "--by", "default_name", default_name)
        assert result.stdout.strip() == session.id

    def test_resolve_any(self, shell_env):
        """Resolving with 'any' (default) tries all fields."""
        session = shell_env.given_session(name="Backend")
        result = shell_env.run("resolve", "Backend")
        assert result.stdout.strip() == session.id

    def test_resolve_ambiguous_name(self, shell_env):
        """Resolving an ambiguous name errors with candidates listed."""
        shell_env.given_session(name="Worker")
        shell_env.given_session(name="Worker")
        result = shell_env.run_expect_error("resolve", "--by", "terminal_name", "Worker")
        assert "multiple sessions match" in result.stderr
        assert "Use --id" in result.stderr


def _extract_field(output: str, field: str) -> str:
    """Extract the first value for a field from key-value record output."""
    for line in output.splitlines():
        if line.startswith(f"{field}: "):
            return line.partition(": ")[2]
    raise ValueError(f"Field '{field}' not found in output:\n{output}")
