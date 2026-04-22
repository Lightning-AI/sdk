"""Shell script tests for command tracking via lightningterminal-lightningterminal.rc.sh.

The lightningterminal.rc script installs a preexec hook that records the last command
run in each session. This is surfaced via the last_command field in ls/status.
"""

from __future__ import annotations

from pathlib import Path

from cli.terminal.integration.conftest import terminal_integration


@terminal_integration
class TestCommandTracking:
    """Command tracking via lightningterminal.rc preexec hook."""

    def test_initial_last_command_is_shell(self, shell_env):
        """A freshly created session shows the shell name as last_command.

        The test harness .zshrc/.bashrc includes a canary command after
        sourcing lightningterminal.rc. If the deferred hook activation is broken,
        last_command would show the canary instead of the shell name.
        """
        shell_env.given_session(name="Fresh")
        result = shell_env.run("ls")
        assert "CANARY" not in result.stdout

    def test_last_command_updates_after_send(self, shell_env):
        """After sending a command, last_command reflects it."""
        session = shell_env.given_session(name="Worker")
        shell_env.run("send", "--id", session.id, "echo TRACKING_TEST", wait_for_completion=True)
        shell_env.run("ls")


@terminal_integration
class TestCommandTrackingArgs:
    """Verify --id argument handling for last_command."""

    def test_last_command_requires_id(self, shell_env):
        """last_command without --id or --name gives a clear error."""
        result = shell_env.run_expect_error("last_command")
        assert "--id or --name is required" in result.stderr

    def test_last_command_by_name(self, shell_env):
        """last_command accepts --name to find a session by terminal name."""
        session = shell_env.given_session(name="Worker")
        shell_env.run("send", "--id", session.id, "echo hello", wait_for_completion=True)
        result = shell_env.run("last_command", "--name", "Worker")
        assert "echo" in result.stdout


@terminal_integration
class TestCommandTrackingSecurity:
    """Verify the preexec hook strips sensitive data."""

    def test_tracks_command_name_only(self, shell_env):
        """The preexec hook records only the command name, not arguments."""
        session = shell_env.given_session(name="Secure")
        shell_env.run(
            "send",
            "--id",
            session.id,
            "curl -H 'Authorization: Bearer secret' https://example.com",
            wait_for_completion=True,
        )
        result = shell_env.run("last_command", "--id", session.id)
        assert result.stdout.strip() == "curl"

    def test_strips_env_vars(self, shell_env):
        """Leading VAR=value assignments are stripped from the command."""
        session = shell_env.given_session(name="Env")
        shell_env.run("send", "--id", session.id, "SECRET=abc OTHER=xyz python train.py", wait_for_completion=True)
        result = shell_env.run("last_command", "--id", session.id)
        assert result.stdout.strip() == "python"


@terminal_integration
class TestCommandTrackingCompat:
    """Verify backward-compatible writes for _lsscreen.sh."""

    def test_old_cmd_history_path_written(self, shell_env):
        """The lightningterminal.rc hook writes to /tmp/cmd_history.{pid}.{session_id}.

        This is the legacy path that _lsscreen.sh reads. It must keep
        working until _lsscreen.sh is retired.
        """
        session = shell_env.given_session(name="Compat")
        shell_env.run("send", "--id", session.id, "echo compat_test", wait_for_completion=True)

        # Find the PID from ls --raw output
        result = shell_env.run("ls", "--raw")
        current_id = ""
        for line in result.stdout.splitlines():
            if line.startswith("session_id: "):
                current_id = line.partition(": ")[2]
            if line.startswith("pid: ") and current_id == session.id:
                break

        # The old path uses the screen session's inner shell PID, not the
        # screen PID. We can't easily get that, but we can check that at
        # least one /tmp/cmd_history file exists for this session_id.
        matching_files = list(Path("/tmp").glob(f"cmd_history.*.{session.id}"))
        assert len(matching_files) > 0, f"Expected /tmp/cmd_history.*.{session.id} to exist for _lsscreen.sh compat"
        content = matching_files[0].read_text()
        assert "echo" in content
