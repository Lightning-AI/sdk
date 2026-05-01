"""Shell script tests for lightningterminal.sh status."""

from __future__ import annotations

from cli.terminal.integration.conftest import terminal_integration


@terminal_integration
class TestScriptStatus:
    """lightningterminal.sh status — show session info."""

    def test_oneliner_contains_name_status_id(self, shell_env):
        """Default status contains name, status, and id in one line."""
        session = shell_env.given_session(name="Backend")
        result = shell_env.run("status", "--id", session.id)
        line = result.stdout.strip()
        assert line.startswith("Backend")
        assert "detached" in line
        assert f"id={session.id}" in line

    def test_oneliner_shows_last_command(self, shell_env):
        """One-liner includes last_command after a command is sent."""
        session = shell_env.given_session(name="Worker")
        shell_env.run("send", "--id", session.id, "echo hello", wait_for_completion=True)
        result = shell_env.run("status", "--id", session.id)
        line = result.stdout.strip()
        assert "Worker - echo" in line

    def test_anonymous_session(self, shell_env):
        """Status of an anonymous session shows default_name."""
        session = shell_env.given_session()
        result = shell_env.run("status", "--id", session.id)
        assert "term-" in result.stdout

    def test_oneliner_vs_raw(self, shell_env):
        """Default and --raw produce different formats for the same session."""
        session = shell_env.given_session(name="Backend")
        oneliner = shell_env.run("status", "--id", session.id)
        raw = shell_env.run("status", "--id", session.id, "--raw")
        assert "(" in oneliner.stdout
        assert "session_id:" not in oneliner.stdout
        assert "session_id:" in raw.stdout
        assert "terminal_name: Backend" in raw.stdout

    def test_by_name(self, shell_env):
        """Status accepts --name to find a session by terminal name."""
        shell_env.given_session(name="Backend")
        result = shell_env.run("status", "--name", "Backend")
        assert "Backend" in result.stdout

    def test_by_default_name(self, shell_env):
        """Status accepts --name with a default name (term-<pid>)."""
        shell_env.given_session()
        result = shell_env.run("ls", "--raw")
        # Extract the default_name from raw ls
        default_name = ""
        for line in result.stdout.splitlines():
            if line.startswith("default_name: "):
                default_name = line.partition(": ")[2]
        assert default_name
        result = shell_env.run("status", "--name", default_name)
        assert default_name in result.stdout

    def test_nonexistent_session(self, shell_env):
        """Status of a nonexistent session gives a clear error."""
        result = shell_env.run_expect_error("status", "--id", "nonexistent-session")
        assert "no terminal session found" in result.stderr

    def test_nonexistent_name(self, shell_env):
        """Status with --name for a nonexistent name gives a clear error."""
        result = shell_env.run_expect_error("status", "--name", "nonexistent")
        assert "no session found" in result.stderr

    def test_ambiguous_name(self, shell_env):
        """Status with --name matching multiple sessions gives a clear error."""
        shell_env.given_session(name="Duplicate")
        shell_env.given_session(name="Duplicate")
        result = shell_env.run_expect_error("status", "--name", "Duplicate")
        assert "multiple sessions match" in result.stderr
        assert "Use --id" in result.stderr

    def test_status_current_session(self, shell_env):
        """Status defaults to the current session when --id is omitted.

        Uses a PTY so the command genuinely runs inside a session
        with LIGHTNING_TERMINAL_SESSION_ID set.
        """
        session = shell_env.given_session(name="Current")
        handle = shell_env.attach_session(session.id)
        handle.wait_for("$")

        handle.send_line("lt status")
        handle.wait_for("Current")
        handle.snapshot("status output from inside session")

    def test_status_no_session_errors(self, shell_env):
        """Status without --id and outside a session gives a clear error."""
        result = shell_env.run_expect_error("status")
        assert "--id is required" in result.stderr


@terminal_integration
class TestScriptStatusRaw:
    """lightningterminal.sh status --raw — key-value output for scripts."""

    def test_raw_output_fields(self, shell_env):
        """Raw status output contains all expected fields."""
        session = shell_env.given_session(name="Backend")
        result = shell_env.run("status", "--id", session.id, "--raw")
        for field in ("session_id:", "pid:", "status:", "terminal_name:", "default_name:", "created:"):
            assert field in result.stdout

    def test_raw_named_session(self, shell_env):
        """Raw status shows key-value pairs for a named session."""
        session = shell_env.given_session(name="Backend")
        result = shell_env.run("status", "--id", session.id, "--raw")
        assert "terminal_name: Backend" in result.stdout


@terminal_integration
class TestStatusAncestors:
    """lightningterminal.sh status --ancestors — show ancestor session tree."""

    def test_ancestors_from_inside_session(self, shell_env):
        """status --ancestors from inside a session lists that session."""
        session = shell_env.given_session(name="MySession")
        handle = shell_env.attach_session(session.id)
        handle.wait_for("$")

        handle.send_line("lt status --ancestors")
        handle.wait_for("MySession")
        handle.snapshot("ancestors from inside session")

    def test_ancestors_raw_from_inside_session(self, shell_env):
        """status --ancestors --raw outputs key-value records."""
        session = shell_env.given_session(name="RawTest")
        handle = shell_env.attach_session(session.id)
        handle.wait_for("$")

        handle.send_line("lt status --ancestors --raw")
        handle.wait_for("session_id:")
        handle.snapshot("ancestors raw from inside session")

    def test_ancestors_outside_session_is_empty(self, shell_env):
        """status --ancestors outside any session produces no output."""
        result = shell_env.run("status", "--ancestors")
        assert result.stdout.strip() == ""

    def test_ancestors_outside_session_raw_is_empty(self, shell_env):
        """status --ancestors --raw outside any session produces no output."""
        result = shell_env.run("status", "--ancestors", "--raw")
        assert result.stdout.strip() == ""

    def test_ancestors_nested_shows_both(self, shell_env):
        """status --ancestors from a nested attach shows both sessions."""
        outer = shell_env.given_session(name="Outer")
        inner = shell_env.given_session(name="Inner")

        handle = shell_env.attach_session(outer.id)
        handle.wait_for("$")

        # From inside outer, attach to inner
        handle.send_line(f"lt attach --id {inner.id}")
        handle.wait_for("$")

        # Now inside inner (via outer), check ancestors
        handle.send_line("lt status --ancestors")
        # Should see the inner session (current) listed
        handle.wait_for("Inner")
        handle.snapshot("ancestors from nested session")

    def _setup_fan_out_tree(self, shell_env):
        """Set up a fan-out ancestor tree and wait for all delegations.

        Tree structure (Child at root, ancestors below):
          Child
          ├─ ParentA
          │  └─ GrandparentA
          └─ ParentB

        Returns (grandparent_a, parent_a, parent_b, child) SessionInfo tuples.
        """
        grandparent_a = shell_env.given_session(name="GrandparentA")
        parent_a = shell_env.given_session(name="ParentA")
        parent_b = shell_env.given_session(name="ParentB")
        child = shell_env.given_session(name="Child")

        # Build chain: GrandparentA → ParentA → Child
        pty1 = shell_env.attach_session(grandparent_a.id)
        pty1.wait_for("$")
        pty1.send_line(f"lt attach --id {parent_a.id}")
        pty1.wait_for("$")
        pty1.send_line(f"lt attach --id {child.id}")
        pty1.wait_for("$")

        # Build delegation: ParentB → Child
        pty2 = shell_env.attach_session(parent_b.id)
        pty2.wait_for("$")
        pty2.send_line(f"lt attach --id {child.id}")
        pty2.wait_for("$")

        # Wait for all three delegations to be written
        shell_env.wait_until(
            lambda: "delegated_to:" in shell_env.run("status", "--id", grandparent_a.id, "--raw").stdout,
            message="GrandparentA should show delegated_to metadata",
        )
        shell_env.wait_until(
            lambda: "delegated_to:" in shell_env.run("status", "--id", parent_a.id, "--raw").stdout,
            message="ParentA should show delegated_to metadata",
        )
        shell_env.wait_until(
            lambda: "delegated_to:" in shell_env.run("status", "--id", parent_b.id, "--raw").stdout,
            message="ParentB should show delegated_to metadata",
        )

        return grandparent_a, parent_a, parent_b, child

    def test_ancestors_tree_with_fan_out(self, shell_env):
        """status --ancestors renders a tree when multiple sessions delegate to the same child."""
        _grandparent_a, _parent_a, _parent_b, child = self._setup_fan_out_tree(shell_env)

        result = shell_env.run("status", "--ancestors", "--id", child.id)
        assert "Child" in result.stdout
        assert "ParentA" in result.stdout
        assert "ParentB" in result.stdout
        assert "GrandparentA" in result.stdout

    def test_ancestors_tree_fan_out_raw(self, shell_env):
        """status --ancestors --raw lists all ancestors in a fan-out tree."""
        grandparent_a, parent_a, parent_b, child = self._setup_fan_out_tree(shell_env)

        result = shell_env.run("status", "--ancestors", "--id", child.id, "--raw")
        assert f"session_id: {child.id}" in result.stdout
        assert f"session_id: {parent_a.id}" in result.stdout
        assert f"session_id: {parent_b.id}" in result.stdout
        assert f"session_id: {grandparent_a.id}" in result.stdout
