"""Shell script tests for lightningterminal.sh detach."""

from __future__ import annotations

from cli.terminal.integration.conftest import terminal_integration


@terminal_integration
class TestScriptDetach:
    """lightningterminal.sh detach — detach from the current session."""

    def test_detach_outside_session_errors(self, shell_env):
        """Detaching when not inside a session gives a clear error."""
        result = shell_env.run_expect_error("detach")
        assert "not inside a session" in result.stderr

    def test_detach_from_attached_session(self, shell_env):
        """Detaching from an attached session returns to the outer shell.

        We attach to a session from inside another session (via PTY),
        then run detach. The outer session's prompt should reappear.
        """
        outer = shell_env.given_session(name="Outer")
        inner = shell_env.given_session(name="Inner")

        handle = shell_env.attach_session(outer.id)
        handle.wait_for("$")

        # Attach to inner from inside outer
        handle.send_line(f"lt attach --id {inner.id}")
        handle.wait_for("$")

        # Detach from inner — should return to outer's shell
        handle.send_line("lt detach")
        handle.wait_for("$")

    def test_detach_restores_status(self, shell_env):
        """After detaching, the inner session shows as detached (verified in-session)."""
        outer = shell_env.given_session(name="Outer")
        inner = shell_env.given_session(name="Inner")

        handle = shell_env.attach_session(outer.id)
        handle.wait_for("$")

        handle.send_line(f"lt attach --id {inner.id}")
        handle.wait_for("$")

        # Verify inner is attached (from inside the PTY)
        handle.send_line(f"lt status --id {inner.id}")
        handle.wait_for("attached")
        handle.snapshot("inner attached")

        # Detach from inner
        handle.send_line("lt detach")
        handle.wait_for("$")

        # Back in outer — verify inner is now detached
        handle.send_line(f"lt status --id {inner.id}")
        handle.wait_for("detached")
        handle.snapshot("inner detached after lt detach")


@terminal_integration
class TestKeyboardDetach:
    """Ctrl+T, D and Ctrl+T, Ctrl+D keyboard shortcuts for detaching.

    These bindings are registered on the screen session at creation time
    and work even when a process is consuming stdin (screen intercepts
    the key sequence at the multiplexer level).

    When sessions are nested (outer delegates to inner), the outer
    session's bindings are temporarily removed so the key sequence
    passes through to the innermost session.
    """

    def test_ctrl_t_d_detaches(self, shell_env):
        """Ctrl+T followed by D detaches from a directly attached session."""
        session = shell_env.given_session(name="Target")
        handle = shell_env.attach_session(session.id)
        handle.wait_for("$")

        # Verify attached inside the session
        handle.send_line("lt status")
        handle.wait_for("attached")

        # Ctrl+T, D detaches — the screen -x process exits,
        # so we verify from outside
        handle.send("\x14d")

        shell_env.wait_until(
            lambda: "detached" in shell_env.run("status", "--id", session.id).stdout,
            message="Session should be detached after Ctrl+T, D",
        )

    def test_ctrl_t_ctrl_d_detaches(self, shell_env):
        """Ctrl+T followed by Ctrl+D detaches from a directly attached session."""
        session = shell_env.given_session(name="Target")
        handle = shell_env.attach_session(session.id)
        handle.wait_for("$")

        handle.send("\x14\x04")

        shell_env.wait_until(
            lambda: "detached" in shell_env.run("status", "--id", session.id).stdout,
            message="Session should be detached after Ctrl+T, Ctrl+D",
        )

    def test_ctrl_t_ctrl_t_sends_literal(self, shell_env):
        """Ctrl+T, Ctrl+T sends a literal Ctrl+T (doesn't detach)."""
        session = shell_env.given_session(name="Typing")
        handle = shell_env.attach_session(session.id)
        handle.wait_for("$")

        # Send Ctrl+T, Ctrl+T — should NOT detach
        handle.send("\x14\x14")

        # Still inside the session — verify by running a command
        handle.send_line("lt status")
        handle.wait_for("attached")
        handle.snapshot("still attached after Ctrl+T Ctrl+T")

    def test_ctrl_t_d_detaches_inner_not_outer(self, shell_env):
        """In nested sessions, Ctrl+T, D detaches from the inner session.

        The outer session's binding is removed during delegation, so the
        key sequence passes through to the inner session which handles it.
        After detach, the outer session's prompt reappears.
        """
        outer = shell_env.given_session(name="Outer")
        inner = shell_env.given_session(name="Inner")

        handle = shell_env.attach_session(outer.id)
        handle.wait_for("$")

        # Attach to inner from inside outer
        handle.send_line(f"lt attach --id {inner.id}")
        handle.wait_for("$")

        # Verify we're in inner
        handle.send_line(f"lt status --id {inner.id}")
        handle.wait_for("attached")

        # Ctrl+T, D should detach from inner, returning to outer
        handle.send("\x14d")
        handle.wait_for("$")

        # Back in outer — verify inner is detached, outer still alive
        handle.send_line(f"lt status --id {inner.id}")
        handle.wait_for("detached")

        handle.send_line(f"lt status --id {outer.id}")
        handle.wait_for("attached")
        handle.snapshot("back in outer after Ctrl+T D")


@terminal_integration
class TestNestedDetach:
    """Deep nesting: attach through multiple levels and detach back."""

    def test_three_levels_deep(self, shell_env):
        """A → attach B → attach C → detach → B → detach → A.

        Verifies that detach unwinds one level at a time through
        nested session attachments.
        """
        a = shell_env.given_session(name="LevelA")
        b = shell_env.given_session(name="LevelB")
        c = shell_env.given_session(name="LevelC")

        handle = shell_env.attach_session(a.id)
        handle.wait_for("$")

        # A → B
        handle.send_line(f"lt attach --id {b.id}")
        handle.wait_for("$")

        # B → C
        handle.send_line(f"lt attach --id {c.id}")
        handle.wait_for("$")

        # Verify we're 3 levels deep: type something in C
        handle.send_line("echo IN_LEVEL_C")
        handle.wait_for("IN_LEVEL_C")
        handle.snapshot("in C")

        # Detach from C → back to B
        handle.send_line("lt detach")
        handle.wait_for("$")
        handle.snapshot("back in B")

        # Detach from B → back to A
        handle.send_line("lt detach")
        handle.wait_for("$")
        handle.snapshot("back in A")

    def test_four_levels_unwind(self, shell_env):
        """A → B → C → D → detach → C → detach → B → detach → A.

        Verifies the session ID changes correctly at each level.
        """
        a = shell_env.given_session(name="L1")
        b = shell_env.given_session(name="L2")
        c = shell_env.given_session(name="L3")
        d = shell_env.given_session(name="L4")

        handle = shell_env.attach_session(a.id)
        handle.wait_for("$")

        # Build nesting: A → B → C → D
        handle.send_line(f"lt attach --id {b.id}")
        handle.wait_for("$")
        handle.send_line(f"lt attach --id {c.id}")
        handle.wait_for("$")
        handle.send_line(f"lt attach --id {d.id}")
        handle.wait_for("$")

        # Verify in D
        handle.send_line("echo SID=$LIGHTNING_TERMINAL_SESSION_ID")
        handle.wait_for(f"SID={d.id}")

        # Unwind: D → C
        handle.send_line("lt detach")
        handle.wait_for("$")
        handle.send_line("echo SID=$LIGHTNING_TERMINAL_SESSION_ID")
        handle.wait_for(f"SID={c.id}")

        # C → B
        handle.send_line("lt detach")
        handle.wait_for("$")
        handle.send_line("echo SID=$LIGHTNING_TERMINAL_SESSION_ID")
        handle.wait_for(f"SID={b.id}")

        # B → A
        handle.send_line("lt detach")
        handle.wait_for("$")
        handle.send_line("echo SID=$LIGHTNING_TERMINAL_SESSION_ID")
        handle.wait_for(f"SID={a.id}")
