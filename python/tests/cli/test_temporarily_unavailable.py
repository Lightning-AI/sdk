from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
import requests
import rich_click as click
from click.testing import CliRunner

from lightning_sdk.cli import lockdown
from lightning_sdk.cli.entrypoint import main_cli
from lightning_sdk.cli.lockdown import GATED_COMMANDS, LOCKDOWN_ENV, UNAVAILABLE_COMMANDS, apply_lockdown
from lightning_sdk.cli.utils.lockdown_status import (
    LOCKDOWN_FLAG,
    STUDIOS_START_STOP_FLAG,
    STUDIOS_SWITCHING_FLAG,
    UPLOADS_FLAG,
)
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.unavailable import is_temporarily_unavailable, mark_temporarily_unavailable
from lightning_sdk.exceptions import RECOVERY_URL, TemporarilyUnavailableError
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from tests.cli.help import command_text

_NOTICE = "is temporarily unavailable."
_PLAIN_NOTICE = f"is temporarily unavailable. Please try again later. More information: {RECOVERY_URL}"


# Commands that call only lockdown-allowed routes or run locally.
_ALLOWED_COMMANDS = (
    "login",
    "logout",
    "ls",
    "teamspace list",
    "machine list",
    "config show",
    "config get user",
    "config set cloud-provider",
    "config set org",
    "license list",
    "completion status",
    "api dockerize",
    "config set studio",
    "config set teamspace",
    "config set user",
    "ssh generate",
    "file download",
    "folder download",
    "cp",
    "studio cp",
    "api deploy",
)


def _resolve(path: str) -> click.Command:
    cmd: click.Command = main_cli
    for name in path.split():
        cmd = cmd.commands[name]  # type: ignore[attr-defined]
    return cmd


@pytest.fixture(autouse=True)
def _fixture_run_commands_unlocked() -> None:
    """Keep the gate on: this module checks it, so it must not be unwrapped as in the other CLI tests."""


@click.command("echo-thing")
@click.option("--name", default="world")
def _echo(name: str) -> None:
    """Echo a greeting."""
    click.echo(f"hello {name}")


def test_marked_command_refuses_to_run() -> None:
    marked = mark_temporarily_unavailable(_echo)

    with click.Context(marked, info_name="echo-thing") as ctx, pytest.raises(TemporarilyUnavailableError) as raised:
        marked.invoke(ctx)

    assert str(raised.value) == f"echo-thing {_PLAIN_NOTICE}"


def test_marked_command_appends_detail() -> None:
    marked = mark_temporarily_unavailable(_echo, detail="Use `other` instead.")

    with click.Context(marked, info_name="echo-thing") as ctx, pytest.raises(TemporarilyUnavailableError) as raised:
        marked.invoke(ctx)

    assert str(raised.value) == f"echo-thing {_PLAIN_NOTICE} Use `other` instead."


def test_original_command_still_runs_after_marking() -> None:
    mark_temporarily_unavailable(_echo)

    result = CliRunner().invoke(_echo, ["--name", "a"], catch_exceptions=False)

    assert result.output == "hello a\n"


def test_marked_command_help_shows_notice_and_original_help() -> None:
    marked = mark_temporarily_unavailable(_echo)

    result = CliRunner().invoke(marked, ["--help"], catch_exceptions=False)

    assert result.exit_code == 0
    assert f"echo-thing {_NOTICE}" in result.output
    assert RECOVERY_URL in result.output
    assert "Echo a greeting." in result.output
    assert "--name" in result.output


_RUN_OPTIONS = ["--name", "test-run", "--image", "ubuntu", "--command", "echo hi"]
_JOB_SDK = "lightning_sdk.cli.job.run.Job"
_MMT_SDK = "lightning_sdk.cli.mmt.run.MMT"
_STUDIO_SDK = "lightning_sdk.cli.studio.start.resolve_studio"
_SANDBOX_SDK = "lightning_sdk.cli.sandbox.commands._sandbox_client"
_DEPLOYMENT_SDK = "lightning_sdk.cli.deployment.create.Deployment"
_VM_SDK = "lightning_sdk.cli.vm.create.VM"
_API_DEPLOY_SDK = "lightning_sdk.cli.api.deploy.api_impl"


@pytest.mark.parametrize(
    ("args", "sdk_target"),
    [
        (["job", "run", *_RUN_OPTIONS], _JOB_SDK),
        (["jobs", "run", *_RUN_OPTIONS], _JOB_SDK),
        (["run", "job", *_RUN_OPTIONS], _JOB_SDK),
        (["mmt", "run", *_RUN_OPTIONS], _MMT_SDK),
        (["run", "mmt", *_RUN_OPTIONS], _MMT_SDK),
        (["studio", "start", "--name", "dev"], _STUDIO_SDK),
        (["start", "studio", "--name", "dev"], _STUDIO_SDK),
        (["sandbox", "run", "sbx-1", "--", "echo", "hi"], _SANDBOX_SDK),
        (["sandboxes", "run", "sbx-1", "--", "echo", "hi"], _SANDBOX_SDK),
        (["sandbox", "create", "--name", "cli-sandbox"], _SANDBOX_SDK),
        (["sandbox", "start", "sbx-1"], _SANDBOX_SDK),
        (["deployment", "create", "--name", "api"], _DEPLOYMENT_SDK),
        (["deployments", "create", "--name", "api"], _DEPLOYMENT_SDK),
        (["vm", "create", "sim-1", "--machine", "H100"], _VM_SDK),
        (["api", "deploy", "server.py", "--cloud"], _API_DEPLOY_SDK),
        (["deploy", "api", "server.py", "--cloud"], _API_DEPLOY_SDK),
        (["api", "deploy", "server.py", "--devbox", "CPU"], _API_DEPLOY_SDK),
    ],
)
def test_execution_commands_are_temporarily_unavailable(args: list[str], sdk_target: str) -> None:
    with patch(sdk_target) as sdk:
        result = CliRunner().invoke(main_cli, args)

    assert result.exit_code == 1
    assert _NOTICE in result.output
    assert sdk.call_count == 0


@pytest.mark.parametrize(
    "command",
    [
        "lightning job run --help",
        "lightning mmt run --help",
        "lightning studio start --help",
        "lightning sandbox run --help",
        "lightning sandbox create --help",
        "lightning sandbox start --help",
        "lightning deployment create --help",
        "lightning vm create --help",
    ],
)
def test_execution_command_help_still_works(command: str) -> None:
    text = command_text(command)

    assert _NOTICE in text
    assert "Usage:" in text


@pytest.mark.parametrize("path", ["studio env", "vm", "sandbox", "code"])
def test_group_whose_commands_are_all_unavailable_says_so_in_help(path: str) -> None:
    result = CliRunner().invoke(main_cli, [*path.split(), "--help"], catch_exceptions=False)

    assert result.exit_code == 0
    assert f"All commands under lightning {path} are temporarily unavailable." in result.output
    assert "Usage:" in result.output


def test_group_with_available_commands_has_no_group_notice() -> None:
    result = CliRunner().invoke(main_cli, ["config", "--help"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "All commands under" not in result.output


@pytest.mark.parametrize("path", UNAVAILABLE_COMMANDS)
def test_every_listed_command_refuses_to_run(path: str) -> None:
    cmd = _resolve(path)
    assert is_temporarily_unavailable(cmd)

    with click.Context(cmd, info_name=path.split()[-1]) as ctx, pytest.raises(TemporarilyUnavailableError):
        cmd.invoke(ctx)


@pytest.mark.parametrize("path", _ALLOWED_COMMANDS)
def test_commands_the_lockdown_allows_stay_runnable(path: str) -> None:
    assert not is_temporarily_unavailable(_resolve(path))


@pytest.mark.parametrize(
    "args",
    [
        ["upload", "file", "a.txt"],
        ["upload", "folder", "a"],
        ["list", "jobs"],
        ["delete", "job", "job-1"],
        ["stop", "studio", "--name", "dev"],
        ["start", "studio", "--name", "dev"],
    ],
)
def test_legacy_forwards_to_unavailable_commands_refuse_to_run(args: list[str]) -> None:
    result = CliRunner().invoke(main_cli, args)

    assert result.exit_code == 1
    assert _NOTICE in result.output


def _set_flags(monkeypatch: pytest.MonkeyPatch, flags: Optional[dict[str, bool]]) -> None:
    """Read ``flags`` as the lockdown's, as if from /v1/config. ``None`` is flags that can't be read."""
    monkeypatch.setattr("lightning_sdk.cli.utils.lockdown_status.lockdown_flags", lambda: flags)


@pytest.mark.parametrize("path", GATED_COMMANDS)
def test_gated_command_is_unavailable_while_its_capability_is_closed(path: str) -> None:
    assert is_temporarily_unavailable(_resolve(path))


@pytest.mark.parametrize(("path", "flags"), GATED_COMMANDS.items())
def test_gated_command_is_available_once_its_capabilities_open(monkeypatch, path: str, flags: tuple[str, ...]) -> None:
    _set_flags(monkeypatch, {LOCKDOWN_FLAG: True, **dict.fromkeys(flags, True)})

    assert not is_temporarily_unavailable(_resolve(path))


def test_studio_create_needs_environment_templates_as_well_as_studios(monkeypatch) -> None:
    _set_flags(monkeypatch, {LOCKDOWN_FLAG: True, STUDIOS_START_STOP_FLAG: True})

    assert is_temporarily_unavailable(_resolve("studio create"))
    assert not is_temporarily_unavailable(_resolve("studio start"))


def test_studio_group_has_no_notice_while_studio_cp_can_download() -> None:
    result = CliRunner().invoke(main_cli, ["studio", "--help"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "All commands under" not in result.output


def test_api_deploy_serves_locally_while_cloud_deploys_are_closed() -> None:
    with patch(_API_DEPLOY_SDK) as sdk:
        result = CliRunner().invoke(main_cli, ["api", "deploy", "server.py"])

    assert result.exit_code == 0, result.output
    assert sdk.call_count == 1


@pytest.mark.parametrize(
    ("args", "uploading"),
    [
        (["studio", "cp", "lit:///studios/dev/a.txt", "a.txt"], False),
        (["studio", "cp", "a.txt", "lit:///studios/dev/a.txt"], True),
    ],
)
def test_studio_cp_refuses_only_uploads_while_uploads_are_closed(args: list[str], uploading: bool) -> None:
    with patch("lightning_sdk.cli.studio.cp._resolve_drive_url", return_value=(MagicMock(), "lit:///x")), patch(
        "lightning_sdk.cli.studio.cp.Filesystem"
    ) as filesystem:
        result = CliRunner().invoke(main_cli, args)

    assert (_NOTICE in result.output) is uploading
    assert filesystem.return_value.copy.call_count == (0 if uploading else 1)


def test_studio_switch_stays_unavailable_while_only_start_and_stop_are_open(monkeypatch) -> None:
    _set_flags(monkeypatch, {LOCKDOWN_FLAG: True, STUDIOS_START_STOP_FLAG: True})

    assert not is_temporarily_unavailable(_resolve("studio start"))
    assert is_temporarily_unavailable(_resolve("studio switch"))
    _set_flags(monkeypatch, {LOCKDOWN_FLAG: True, STUDIOS_START_STOP_FLAG: True, STUDIOS_SWITCHING_FLAG: True})
    assert not is_temporarily_unavailable(_resolve("studio switch"))


@pytest.mark.parametrize("path", ["job run", "studio start", "rm"])
def test_every_marked_command_is_available_once_the_lockdown_is_off(monkeypatch, path: str) -> None:
    _set_flags(monkeypatch, {LOCKDOWN_FLAG: False})

    assert not is_temporarily_unavailable(_resolve(path))


def test_unreadable_flags_keep_the_always_unavailable_commands_refused_and_let_gated_ones_run(monkeypatch) -> None:
    _set_flags(monkeypatch, None)

    assert is_temporarily_unavailable(_resolve("job run"))
    assert not is_temporarily_unavailable(_resolve("studio start"))


def test_rm_runs_once_uploads_open(monkeypatch) -> None:
    _set_flags(monkeypatch, {LOCKDOWN_FLAG: True, UPLOADS_FLAG: True})

    with patch("lightning_sdk.cli.rm.Filesystem") as filesystem:
        result = CliRunner().invoke(main_cli, ["rm", "lit:///uploads/a.txt"])

    assert result.exit_code == 0, result.output
    filesystem.return_value.rm.assert_called_once()


def test_rm_refuses_to_run_while_uploads_are_closed() -> None:
    with patch("lightning_sdk.cli.rm.Filesystem") as filesystem:
        result = CliRunner().invoke(main_cli, ["rm", "lit:///uploads/a.txt"])

    assert result.exit_code == 1
    assert _NOTICE in result.output
    assert filesystem.call_count == 0


def test_cp_downloads_while_uploads_are_closed() -> None:
    with patch("lightning_sdk.cli.cp.Filesystem") as filesystem:
        result = CliRunner().invoke(main_cli, ["cp", "lit:///uploads/a.txt", "a.txt"])

    assert result.exit_code == 0, result.output
    filesystem.return_value.copy.assert_called_once()


def test_cp_refuses_to_upload_while_uploads_are_closed() -> None:
    with patch("lightning_sdk.cli.cp.Filesystem") as filesystem:
        result = CliRunner().invoke(main_cli, ["cp", "a.txt", "lit:///uploads/a.txt"])

    assert result.exit_code == 1
    assert _NOTICE in result.output
    assert filesystem.call_count == 0


def test_cp_uploads_once_uploads_open(monkeypatch) -> None:
    _set_flags(monkeypatch, {LOCKDOWN_FLAG: True, UPLOADS_FLAG: True})

    with patch("lightning_sdk.cli.cp.Filesystem") as filesystem:
        result = CliRunner().invoke(main_cli, ["cp", "a.txt", "lit:///uploads/a.txt"])

    assert result.exit_code == 0, result.output
    filesystem.return_value.copy.assert_called_once()


def test_group_notice_goes_once_one_of_its_commands_is_available(monkeypatch) -> None:
    _set_flags(monkeypatch, {LOCKDOWN_FLAG: True, STUDIOS_START_STOP_FLAG: True})

    result = CliRunner().invoke(main_cli, ["studio", "--help"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "All commands under" not in result.output


def test_help_of_an_available_gated_command_has_no_notice(monkeypatch) -> None:
    _set_flags(monkeypatch, {LOCKDOWN_FLAG: True, STUDIOS_START_STOP_FLAG: True})

    text = command_text("lightning studio start --help")

    assert _NOTICE not in text
    assert "Usage:" in text


def _api_exception(status: int, content_type: str, body: bytes) -> ApiException:
    error = ApiException(status=status, reason="Forbidden")
    error.headers = {"Content-Type": content_type}
    error.body = body
    return error


def _http_error(status: int, content_type: str, body: bytes) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    response.headers["Content-Type"] = content_type
    response._content = body
    return requests.HTTPError(response=response)


def _raising(error: Exception) -> click.Command:
    @click.command("fetch-thing", cls=LightningCommand)
    def _fetch() -> None:
        try:
            raise error
        except Exception as e:
            raise RuntimeError("could not fetch the thing") from e

    return _fetch


@pytest.mark.parametrize(
    "error",
    [
        _api_exception(403, "text/html; charset=UTF-8", b"<html>Sorry, you have been blocked</html>"),
        _api_exception(403, "application/json", b'{"code":7,"message":"this API is not available during maintenance"}'),
        _http_error(403, "text/plain; charset=utf-8", b"this API is not available during maintenance\n"),
    ],
)
def test_a_lockdown_refusal_shows_the_notice(error: Exception) -> None:
    result = CliRunner().invoke(_raising(error), [])

    assert result.exit_code == 1
    assert f"fetch-thing {_NOTICE}" in click.unstyle(result.output)


@pytest.mark.parametrize(
    "error",
    [
        _api_exception(403, "application/json", b'{"code":7,"message":"permission denied"}'),
        _http_error(404, "text/html", b"<html>Not found</html>"),
    ],
)
def test_other_errors_are_not_mistaken_for_a_lockdown_refusal(error: Exception) -> None:
    result = CliRunner().invoke(_raising(error), [])

    assert isinstance(result.exception, RuntimeError)
    assert _NOTICE not in result.output


@pytest.mark.parametrize(
    ("value", "locked"),
    [(None, True), ("", True), ("1", True), ("true", True), ("0", False), ("false", False)],
)
def test_lockdown_env_controls_the_gate(monkeypatch, value: str | None, locked: bool) -> None:
    if value is None:
        monkeypatch.delenv(LOCKDOWN_ENV, raising=False)
    else:
        monkeypatch.setenv(LOCKDOWN_ENV, value)
    monkeypatch.setattr(lockdown, "UNAVAILABLE_COMMANDS", ("echo-thing",))
    monkeypatch.setattr(lockdown, "GATED_COMMANDS", {})
    monkeypatch.setattr(lockdown, "PARAM_GATED_COMMANDS", {})
    root = click.Group("root")
    root.add_command(_echo)

    apply_lockdown(root)

    assert is_temporarily_unavailable(root.commands["echo-thing"]) is locked
    if not locked:
        result = CliRunner().invoke(root, ["echo-thing", "--name", "a"], catch_exceptions=False)
        assert result.output == "hello a\n"
