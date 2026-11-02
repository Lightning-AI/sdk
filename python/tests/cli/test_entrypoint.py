import os
import re
import subprocess
from unittest.mock import MagicMock, patch

import pytest
import rich_click as click
from click.testing import CliRunner

from lightning_sdk.cli.entrypoint import login, main_cli
from lightning_sdk.cli.sandbox.commands import run_sandbox_command
from lightning_sdk.cli.vm.ssh import ssh_vm
from lightning_sdk.lightning_cloud.login import Auth
from tests.cli.help import assert_help_contains, command_text, mock_command_logging, run_cli

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_BOX_CHARS_RE = re.compile(r"[│╭╰╮─╯]")


def _clear_auth(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(Auth, "secrets_file", tmp_path / "credentials.json")
    monkeypatch.delenv("LIGHTNING_USER_ID", raising=False)
    monkeypatch.delenv("LIGHTNING_API_KEY", raising=False)
    monkeypatch.delenv("LIGHTNING_AUTH_TOKEN", raising=False)


@pytest.mark.parametrize(
    ("cli", "args"),
    [
        (main_cli, ["teamspace", "list"]),
        (main_cli, ["ls", "lit://owner/teamspace/"]),
    ],
)
def test_resource_commands_never_start_browser_authentication(monkeypatch, tmp_path, cli, args) -> None:
    _clear_auth(monkeypatch, tmp_path)
    monkeypatch.setattr(
        Auth,
        "_run_server",
        lambda _self: (_ for _ in ()).throw(AssertionError("browser auth reached")),
    )

    result = CliRunner().invoke(cli, args)

    assert result.exit_code == 1
    assert "Run `lightning login`" in str(result.exception)


def test_explicit_login_can_start_browser_authentication(monkeypatch, tmp_path) -> None:
    _clear_auth(monkeypatch, tmp_path)
    browser_auth_started = False

    def _complete_browser_auth(auth: Auth) -> None:
        nonlocal browser_auth_started
        browser_auth_started = True
        auth.api_key = "api-key"

    monkeypatch.setattr(Auth, "_run_server", _complete_browser_auth)

    result = CliRunner().invoke(main_cli, ["login"])

    assert result.exit_code == 0, result.output
    assert browser_auth_started


def test_login_reports_success_and_failure(monkeypatch, tmp_path) -> None:
    _clear_auth(monkeypatch, tmp_path)
    user = MagicMock()
    user.name = "Test User"
    monkeypatch.setattr("lightning_sdk.cli.entrypoint._get_authed_user", lambda: user)

    def _save_token(auth: Auth) -> None:
        auth.save(token="sess_user-1.secret", user_id="user-1")

    monkeypatch.setattr(Auth, "_run_server", _save_token)
    ok = CliRunner().invoke(main_cli, ["login"])
    assert ok.exit_code == 0, ok.output
    assert 'Successfully logged in as "Test User".' in ok.output

    # the browser callback finished without saving a token
    _clear_auth(monkeypatch, tmp_path / "second")
    monkeypatch.setattr(Auth, "_run_server", lambda _auth: None)
    failed = CliRunner().invoke(main_cli, ["login"])
    assert failed.exit_code == 1
    assert "Login failed" in str(failed.exception)


def test_login_device_starts_a_fresh_device_login_instead_of_the_browser(monkeypatch, tmp_path) -> None:
    _clear_auth(monkeypatch, tmp_path)
    Auth().save(auth_token="sess_expired")
    user = MagicMock()
    user.name = "Test User"
    monkeypatch.setattr("lightning_sdk.cli.entrypoint._get_authed_user", lambda: user)
    monkeypatch.setattr(
        Auth,
        "_run_server",
        lambda _self: (_ for _ in ()).throw(AssertionError("browser auth reached")),
    )

    def _approve(auth: Auth) -> None:
        assert not Auth.secrets_file.exists()
        auth.save(auth_token="sess_new")

    monkeypatch.setattr("lightning_sdk.cli.entrypoint.login_with_device_code", _approve)

    result = CliRunner().invoke(main_cli, ["login", "--device"])

    assert result.exit_code == 0, result.output
    assert 'Successfully logged in as "Test User".' in result.output
    auth = Auth()
    assert auth.load()
    assert auth.auth_token == "sess_new"


def test_logout_reports_success_and_failure(monkeypatch, tmp_path) -> None:
    _clear_auth(monkeypatch, tmp_path)
    ok = CliRunner().invoke(main_cli, ["logout"])
    assert ok.exit_code == 0, ok.output
    assert "Successfully logged out." in ok.output

    monkeypatch.setattr("lightning_sdk.cli.entrypoint.logout_session", MagicMock(side_effect=OSError("denied")))
    failed = CliRunner().invoke(main_cli, ["logout"])
    assert failed.exit_code == 1
    assert "Logout failed: denied" in str(failed.exception)


def test_cli_browser_auth_policy_is_reset_after_command(monkeypatch, tmp_path) -> None:
    _clear_auth(monkeypatch, tmp_path)
    browser_auth_starts = 0

    def _complete_browser_auth(auth: Auth) -> None:
        nonlocal browser_auth_starts
        browser_auth_starts += 1
        auth.api_key = "api-key"

    monkeypatch.setattr(Auth, "_run_server", _complete_browser_auth)

    result = CliRunner().invoke(main_cli, ["job", "list", "--teamspace", "owner/teamspace"])

    assert result.exit_code == 1
    assert "Run `lightning login`" in str(result.exception)
    assert browser_auth_starts == 0
    assert Auth().authenticate().startswith("Bearer ")
    assert browser_auth_starts == 1


def _help_text() -> str:
    """Return help output with each command's wrapped description joined onto one line.

    The rich-click layout renders two side-by-side panels separated by ││.
    We split each row into left and right cells, process each column
    independently so that continuation lines (leading spaces > 3) are merged
    into the preceding command entry, and return the reconstructed lines.
    """
    result = run_cli("lightning --help")
    raw = _ANSI_ESCAPE_RE.sub("", result.stdout)

    # Locate the column split from the first row that contains ││
    split = -1
    for line in raw.splitlines():
        pos = line.find("││")
        if pos >= 0:
            split = pos + 1
            break

    left_cells: list[tuple[str, bool]] = []
    right_cells: list[tuple[str, bool]] = []
    for line in raw.splitlines():
        is_panel = "│" in line
        if split > 0 and len(line) > split and is_panel:
            left_cells.append((line[:split], True))
            right_cells.append((line[split:], True))
        else:
            left_cells.append((line, False))
            right_cells.append(("", False))

    def _join_cells(cells: list[tuple[str, bool]]) -> list[str]:
        entries: list[str] = []
        for cell, is_panel in cells:
            content = _BOX_CHARS_RE.sub(" ", cell)
            stripped = content.lstrip()
            leading = len(content) - len(stripped)
            value = stripped.rstrip()
            if not value:
                continue
            # Panel continuation lines have the command-name column empty (> 3 spaces).
            # Non-panel lines (headers, usage, separators) are never continuations.
            if is_panel and leading > 3 and entries:
                entries[-1] = entries[-1].rstrip() + " " + value
            else:
                entries.append(value)
        return entries

    return "\n".join(_join_cells(left_cells) + _join_cells(right_cells))


@mock_command_logging
def test_help():
    text = _help_text()

    assert "Usage: lightning [OPTIONS] COMMAND [ARGS]..." in text

    # GET STARTED
    assert "login     Sign in to Lightning AI." in text
    assert "logout    Sign out of the current session." in text
    assert "config    Manage SDK and CLI settings." in text

    # COMPUTE
    assert "studio    Persistent GPU dev workspaces." in text
    assert "base-st…  Reusable Studio environment images." in text
    assert "machine   Browse GPU and CPU machine types." in text
    assert "contain…  Run and manage containers." in text
    assert "sandbox   Ephemeral sandboxes for agents." in text

    # TRAIN & DEPLOY
    assert "job       Run batch jobs and sweeps." in text
    assert "mmt       Multi-node distributed training." in text
    assert "model     Register and version models." in text
    assert "deploym…  Deploy autoscaling inference APIs." in text

    # ACCESS
    assert "ssh       Configure SSH access to Studios." in text
    assert "license   View and manage product licenses." in text

    # DATA & FILES
    assert "cp        Copy between local, Studios, Drive." in text
    assert "connect…  Work with teamspace data connections." in text

    # Deprecated commands should not appear
    assert "file      Upload and download files." not in text
    assert "folder    Upload and download folders." not in text

    # Hidden commands should not appear
    assert "  create" not in text
    assert "  delete" not in text
    assert "  download" not in text
    assert not any(line.startswith("  api ") for line in text.splitlines())
    assert "  jobs" not in text
    assert "  open" not in text
    assert "  run" not in text
    assert "  studios" not in text
    assert "  upload" not in text


@mock_command_logging
def test_help_uvx():
    result = subprocess.run("uvx --with-editable=../ lightning-sdk --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    if "Usage: lightning-sdk [OPTIONS] COMMAND [ARGS]..." in result_text:
        assert not any(line.startswith("  api ") for line in result_text.splitlines())
        assert "cp        Copy between local," in result_text
        assert "contain…  Run and manage containers." in result_text
        assert "job       Run batch jobs and sweeps." in result_text
        assert "license   View and manage product" in result_text
        assert "machine   Browse GPU and CPU machine" in result_text
        assert "mmt       Multi-node distributed" in result_text
        assert "sandbox   Ephemeral sandboxes for" in result_text
        assert "ssh       Configure SSH access to" in result_text
        assert "studio    Persistent GPU dev" in result_text
        return


@pytest.mark.parametrize(
    ("command", "args", "forwarded_to", "expected"),
    [
        (ssh_vm, ["myvm", "-h"], "ssh_args", ("-h",)),
        (run_sandbox_command, ["sbx-42", "du", "-h", "/data"], "command_args", ("du", "-h", "/data")),
    ],
)
@mock_command_logging
def test_pass_through_commands_forward_h_to_the_wrapped_program(command, args, forwarded_to, expected) -> None:
    """`-h` is a flag of the program being wrapped, so these commands must not treat it as help."""
    # The parent context is where `-h` would otherwise be inherited from.
    context = command.make_context(command.name, args, parent=click.Context(main_cli))

    assert context.params[forwarded_to] == expected


@pytest.mark.parametrize(
    "command",
    [
        "lightning",
        "lightning job",
        "lightning job list",
        "lightning jobs list",
        "lightning login",
    ],
)
@mock_command_logging
def test_short_help_flag_matches_long(command: str) -> None:
    """`-h` is an alias of `--help`, except on the pass-through commands tested above."""
    assert command_text(f"{command} -h") == command_text(f"{command} --help")


@mock_command_logging
def test_login_help():
    result_text = assert_help_contains("lightning login --help", "Usage: lightning login [OPTIONS]")

    assert "Sign in to Lightning AI." in result_text
    assert "--device" in result_text


@mock_command_logging
def test_logout_help():
    result_text = assert_help_contains("lightning logout --help", "Usage: lightning logout [OPTIONS]")

    assert "Sign out of the current session." in result_text


def test_login_replaces_existing_session(monkeypatch, tmp_path):
    _clear_auth(monkeypatch, tmp_path)
    Auth().save(auth_token="sess_expired")

    def _complete_browser_auth(auth: Auth) -> None:
        assert not Auth.secrets_file.exists()
        auth.save(auth_token="sess_new")

    monkeypatch.setattr(Auth, "_run_server", _complete_browser_auth)

    result = CliRunner().invoke(main_cli, ["login"])

    assert result.exit_code == 0, result.output
    auth = Auth()
    assert auth.load()
    assert auth.auth_token == "sess_new"


@pytest.mark.parametrize("env_var", ["LIGHTNING_AUTH_TOKEN", "LIGHTNING_API_KEY"])
def test_login_not_required_with_credentials_in_env(monkeypatch, tmp_path, env_var):
    _clear_auth(monkeypatch, tmp_path)
    monkeypatch.setenv(env_var, "from-env")
    Auth().save(auth_token="sess_saved")

    def _fail_browser_auth(auth: Auth) -> None:
        raise AssertionError("browser authentication should not start")

    monkeypatch.setattr(Auth, "_run_server", _fail_browser_auth)

    result = CliRunner().invoke(main_cli, ["login"])

    assert result.exit_code == 0, result.output
    assert "credentials are set in the environment" in result.output
    assert Auth.secrets_file.exists()


@patch.dict(os.environ, {"LIGHTNING_INTERACTIVE": "true", "LIGHTNING_CLOUD_SPACE_ID": "cloud-space-id"}, clear=True)
@mock_command_logging
def test_cannot_login_within_studio_without_credentials(monkeypatch):
    mock_auth_instance = MagicMock(api_key=None, auth_token=None)
    monkeypatch.setattr("lightning_sdk.cli.entrypoint.Auth", MagicMock(return_value=mock_auth_instance))

    result = CliRunner().invoke(login)

    assert result.exit_code == 1
    assert "Unable to login within a Studio. Did you change your shell setup?" in str(result.exception)
    mock_auth_instance.authenticate.assert_not_called()
