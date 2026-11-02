from unittest.mock import patch

import pytest
import rich_click as click
from click.testing import CliRunner

from lightning_sdk.cli.entrypoint import main_cli
from lightning_sdk.cli.lockdown import UNAVAILABLE_COMMANDS
from lightning_sdk.cli.utils.unavailable import is_temporarily_unavailable, mark_temporarily_unavailable
from lightning_sdk.exceptions import RECOVERY_URL, TemporarilyUnavailableError
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
        (["api", "deploy", "server.py"], _API_DEPLOY_SDK),
        (["deploy", "api", "server.py"], _API_DEPLOY_SDK),
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
        "lightning api deploy --help",
    ],
)
def test_execution_command_help_still_works(command: str) -> None:
    text = command_text(command)

    assert _NOTICE in text
    assert "Usage:" in text


@pytest.mark.parametrize("path", ["studio", "studio env", "vm", "container"])
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
        ["download", "file", "lit:///a.txt", "a.txt"],
        ["upload", "file", "a.txt"],
        ["download", "folder", "lit:///a", "a"],
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
