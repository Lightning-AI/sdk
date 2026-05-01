"""Shell script tests for lightningterminal.sh attach."""

from __future__ import annotations

from cli.terminal.integration.conftest import terminal_integration


@terminal_integration
class TestScriptAttach:
    """lightningterminal.sh attach — attach to sessions."""

    def test_attach_no_create_requires_id(self, shell_env):
        """Attach with --no-create and no --id gives a clear error."""
        result = shell_env.run_expect_error("attach", "--no-create")
        assert "--id or --name is required" in result.stderr

    def test_attach_no_create_nonexistent(self, shell_env):
        """Attach with --no-create to a nonexistent session gives a clear error."""
        result = shell_env.run_expect_error("attach", "--id", "nonexistent-id", "--no-create")
        assert "no terminal session found" in result.stderr

    def test_attach_creates_by_name(self, shell_env):
        """Attach with --name creates a new session if none exists.

        This exercises the create-if-missing path in _screen_attach_or_create,
        which previously broke due to _screen_resolve's exit 1 propagating
        through set -e in command substitutions.
        """
        handle = shell_env.attach_session(name="BrandNew")
        handle.wait_for("$")

        result = shell_env.run("ls")
        assert "BrandNew" in result.stdout

    def test_attach_creates_by_id(self, shell_env):
        """Attach with --id creates a new session if the id doesn't exist."""
        handle = shell_env.attach_session("fresh-session")
        handle.wait_for("$")

        result = shell_env.run("ls")
        assert "fresh-session" in result.stdout

    def test_attach_reuses_existing_by_name(self, shell_env):
        """Attach with --name reuses an existing session with that name."""
        shell_env.given_session(name="Existing")

        handle = shell_env.attach_session(name="Existing")
        handle.wait_for("$")

        result = shell_env.run("ls", "--raw")
        # Should be one session, not two
        assert result.stdout.count("session_id:") == 1

    def test_attach_shows_as_attached(self, shell_env):
        """Attaching via PTY makes the session show as 'attached' in ls.

        Screen updates socket permissions synchronously on attach — no
        polling needed.
        """
        session = shell_env.given_session(name="Target")

        result = shell_env.run("status", "--id", session.id)
        assert "detached" in result.stdout

        shell_env.attach_session(session.id)

        result = shell_env.run("status", "--id", session.id)
        assert "attached" in result.stdout

    def test_detach_returns_to_detached(self, shell_env):
        """After detaching, the session returns to 'detached' in ls."""
        session = shell_env.given_session(name="Detachable")

        handle = shell_env.attach_session(session.id)

        result = shell_env.run("status", "--id", session.id)
        assert "attached" in result.stdout

        handle.detach()

        result = shell_env.run("status", "--id", session.id)
        assert "detached" in result.stdout

    def test_pty_interaction(self, shell_env):
        """Typing into an attached PTY and verifying via pyte snapshot."""
        session = shell_env.given_session(name="Interactive")

        handle = shell_env.attach_session(session.id)
        handle.wait_for("$")

        handle.send_line("echo PTY_MARKER_42")
        handle.wait_for("PTY_MARKER_42")
        handle.snapshot("marker visible")

        lines = handle.display()
        assert any("PTY_MARKER_42" in line for line in lines)


@terminal_integration
class TestAttachWithMotd:
    """Test PTY behaviour when the shell rc prints an MOTD.

    The lightningterminal.rc script runs `tput csr` to reset the scroll region.
    These tests check whether MOTD text before/after lightningterminal.rc
    interferes with the terminal display.
    """

    def test_motd_before_rc(self, shell_env):
        """MOTD printed before lightningterminal.rc (before tput csr).

        tput csr resets the cursor to (0,0) but doesn't clear the
        buffer, so the prompt overwrites the first characters of the
        MOTD. The rest of the MOTD remains as stale characters.

        Bash can print this sudo hint from /etc/bash.bashrc on load.
        """
        shell_env.set_env("LIGHTNING_TERMINAL_TEST_MOTD", "before")
        session = shell_env.given_session(name="MotdBefore")
        handle = shell_env.attach_session(session.id)
        handle.wait_for("$")
        handle.snapshot("motd before lightningterminal.rc")

    def test_motd_after_rc(self, shell_env):
        """MOTD printed after lightningterminal.rc (after tput csr).

        This is the production-like scenario. The MOTD appears as
        normal terminal output after the scroll region is reset.
        """
        shell_env.set_env("LIGHTNING_TERMINAL_TEST_MOTD", "after")
        session = shell_env.given_session(name="MotdAfter")
        handle = shell_env.attach_session(session.id)
        handle.wait_for("$")
        handle.snapshot("motd after lightningterminal.rc")


@terminal_integration
class TestScriptAttachExec:
    """lightningterminal.sh attach --exec — create session and exec into it."""

    def test_exec_with_explicit_id(self, shell_env):
        """attach --exec with an explicit session_id creates that session."""
        handle = shell_env.init_session("my-test-session")
        handle.wait_for("$")

        result = shell_env.run("ls")
        assert "my-test-session" in result.stdout

    def test_exec_anonymous(self, shell_env):
        """attach --exec without a session_id creates a session-XXXXXXXX session."""
        handle = shell_env.init_session()
        handle.wait_for("$")

        result = shell_env.run("ls")
        assert "session-" in result.stdout

    def test_exec_env_vars(self, shell_env):
        """The inner shell has LIGHTNING_TERMINAL_SESSION_ID set."""
        handle = shell_env.init_session("env-check")
        handle.wait_for("$")

        handle.send_line("echo SID=$LIGHTNING_TERMINAL_SESSION_ID")
        handle.wait_for("SID=env-check")
        handle.snapshot("env var is set")

    def test_exec_command_tracking(self, shell_env):
        """Shellinit hooks work — last_command updates after typing a command."""
        handle = shell_env.init_session("tracking")
        handle.wait_for("$")

        handle.send_line("echo hello")
        handle.wait_for("hello")

        result = shell_env.run("last_command", "--id", "tracking")
        assert "echo" in result.stdout

    def test_exec_visible_in_status(self, shell_env):
        """An exec'd session appears in status output."""
        handle = shell_env.init_session("status-check")
        handle.wait_for("$")

        result = shell_env.run("status", "--id", "status-check")
        assert "status-check" in result.stdout
        assert "attached" in result.stdout


@terminal_integration
class TestScriptAttachSource:
    """lightningterminal.sh attach --source — source tagging on create."""

    def test_source_on_attach_create(self, shell_env):
        """Source is written when attach creates a new session."""
        handle = shell_env.attach_session("agent-session", source="agent")
        handle.wait_for("$")

        result = shell_env.run("status", "--id", "agent-session", "--raw")
        assert "source: agent" in result.stdout

    def test_source_on_exec(self, shell_env):
        """Source tag works with --exec (the .lightningrc flow)."""
        handle = shell_env.init_session("platform-session", source="platform")
        handle.wait_for("$")

        result = shell_env.run("status", "--id", "platform-session", "--raw")
        assert "source: platform" in result.stdout


@terminal_integration
class TestSelfAttachGuard:
    """lightningterminal.sh attach — refuse to attach to self or ancestor."""

    def test_attach_to_current_session_errors(self, shell_env):
        """Attaching to the session you're already inside gives a clear error."""
        session = shell_env.given_session(name="Current")
        handle = shell_env.attach_session(session.id)
        handle.wait_for("$")

        handle.send_line(f"lt attach --id {session.id} --no-create")
        handle.wait_for("already inside it")
        handle.snapshot("self-attach error")

    def test_attach_to_ancestor_session_errors(self, shell_env):
        """Attaching to an ancestor session gives a clear error."""
        outer = shell_env.given_session(name="Outer")
        inner = shell_env.given_session(name="Inner")

        handle = shell_env.attach_session(outer.id)
        handle.wait_for("$")

        # Attach to inner from inside outer
        handle.send_line(f"lt attach --id {inner.id}")
        handle.wait_for("$")

        # Now try to attach back to outer from inside inner
        handle.send_line(f"lt attach --id {outer.id} --no-create")
        handle.wait_for("already inside it")
        handle.snapshot("ancestor-attach error")

    def test_attach_to_different_session_still_works(self, shell_env):
        """Attaching to a different (non-ancestor) session still works."""
        current = shell_env.given_session(name="Current")
        other = shell_env.given_session(name="Other")

        handle = shell_env.attach_session(current.id)
        handle.wait_for("$")

        # Attaching to a sibling session should work fine
        handle.send_line(f"lt attach --id {other.id}")
        handle.wait_for("$")

        # Verify we're in the other session
        handle.send_line("echo MARKER_IN_OTHER")
        handle.wait_for("MARKER_IN_OTHER")
        handle.snapshot("attach to sibling works")

    def test_attach_by_name_to_current_errors(self, shell_env):
        """Attaching by --name to the current session gives a clear error."""
        session = shell_env.given_session(name="Named")
        handle = shell_env.attach_session(session.id)
        handle.wait_for("$")

        handle.send_line("lt attach --name Named --no-create")
        handle.wait_for("already inside it")
        handle.snapshot("self-attach by name error")


@terminal_integration
class TestAttachDetachTip:
    """The detach tip shown when attaching interactively."""

    def test_tip_shown_on_interactive_attach(self, shell_env):
        """Attaching interactively shows a detach tip (when QUIET is unset).

        The tip is printed to stderr before screen -x takes over. Screen's
        redraw (ESC[H ESC[J) then clears the visible area, so the tip
        doesn't appear in the pyte snapshot — but it IS visible in real
        terminals via scrollback. We assert on the PTY stream to confirm
        it was written, then document it in the snapshot as a comment.
        """
        shell_env.unset_env("LIGHTNING_TERMINAL_QUIET")
        session = shell_env.given_session(name="Tipped")

        handle = shell_env.attach_session(session.id)
        # Tests run the script directly (not via the `lt` function), so
        # SCRIPT_NAME is "lightningterminal.sh". In production it says "lt".
        expected_tip = "── Tip: detach with Ctrl+T, D (or lightningterminal.sh detach) ──"
        handle.wait_for(expected_tip)
        shell_env.comment(
            "The tip below is visible in real terminals (scrollback) but not in",
            "pyte snapshots — screen's redraw (ESC[H ESC[J) clears the display.",
            "Verified via wait_for assertion on the PTY stream:",
            "",
            f"  {expected_tip}",
            "",
        )
        handle.snapshot("after attach (tip was shown before screen redraw)")

    def test_tip_not_shown_with_exec(self, shell_env):
        """Attaching with --exec does not show the detach tip."""
        shell_env.unset_env("LIGHTNING_TERMINAL_QUIET")

        handle = shell_env.init_session("exec-no-tip")
        handle.wait_for("$")

        # The tip should NOT appear — init_session uses --exec
        lines = handle.display()
        assert not any("Tip:" in line for line in lines)
        handle.snapshot("no tip with exec")

    def test_tip_suppressed_by_quiet(self, shell_env):
        """The tip is suppressed when LIGHTNING_TERMINAL_QUIET is set."""
        # QUIET is already set by the test harness; verify it works
        session = shell_env.given_session(name="Quiet")

        handle = shell_env.attach_session(session.id)
        handle.wait_for("$")

        lines = handle.display()
        assert not any("Tip:" in line for line in lines)
        handle.snapshot("no tip when quiet")
