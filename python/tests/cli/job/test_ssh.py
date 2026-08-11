from unittest.mock import MagicMock, patch

import pytest
import rich_click as click
from click.testing import CliRunner

from lightning_sdk.cli.job.ssh import ssh_impl, ssh_job
from lightning_sdk.cli.utils.ssh_connection import _job_ssh_user
from lightning_sdk.mmt import MMT
from lightning_sdk.status import Status
from tests.cli.help import assert_help_contains, command_text, mock_command_logging


@pytest.mark.parametrize(
    ("job_id", "expected"),
    [
        ("job_01jj4hvvjj4zx1t1esm5az3zt7", "j_01jj4hvvjj4zx1t1esm5az3zt7"),
        ("01jj4hvvjj4zx1t1esm5az3zt7", "j_01jj4hvvjj4zx1t1esm5az3zt7"),
    ],
)
def test_ssh_user_for_job_id(job_id: str, expected: str) -> None:
    assert _job_ssh_user(job_id) == expected


@mock_command_logging
def test_job_ssh_help() -> None:
    result_text = command_text("lightning job ssh --help")

    assert "Usage: lightning job ssh [OPTIONS] NAME" in result_text
    assert "SSH into a running job." in result_text
    assert "--teamspace" in result_text
    assert "--rank" in result_text


@mock_command_logging
def test_jobs_ssh_help() -> None:
    assert_help_contains("lightning jobs ssh --help", "Usage: lightning jobs ssh", "SSH into a running job.")


def test_ssh_resolves_before_downloading_keys() -> None:
    """SSH lookup failures occur before key downloads."""
    exec_mock = MagicMock()
    with patch(
        "lightning_sdk.cli.job.ssh.resolve_teamspace",
        return_value=MagicMock(name="coding-model-training"),
    ), patch(
        "lightning_sdk.cli.job.ssh.resolve_job",
        side_effect=click.UsageError("Could not resolve job 'missing'."),
    ), patch(
        "lightning_sdk.cli.job.ssh.exec_ssh",
        exec_mock,
    ), pytest.raises(click.UsageError, match="Could not resolve job"):
        ssh_impl(name="missing", teamspace=None)

    exec_mock.assert_not_called()


def test_ssh_rejects_non_running_job() -> None:
    job = MagicMock()
    job.name = "train"
    job.status = Status.Completed
    job.id = "job_01abc"

    with patch("lightning_sdk.cli.job.ssh.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.job.ssh.resolve_job", return_value=job
    ), patch("lightning_sdk.cli.job.ssh.exec_ssh") as exec_mock, pytest.raises(
        click.ClickException, match="not Running"
    ):
        ssh_impl(name="train", teamspace=None)

    exec_mock.assert_not_called()


def test_ssh_runs_against_job_gateway_user() -> None:
    teamspace = MagicMock()
    job = MagicMock()
    job.name = "train"
    job.status = Status.Running
    job.id = "job_01jj4hvvjj4zx1t1esm5az3zt7"

    with patch("lightning_sdk.cli.job.ssh.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.ssh.resolve_job", return_value=job
    ) as resolve_job, patch(
        "lightning_sdk.cli.utils.ssh_connection.configure_ssh_internal", return_value="/tmp/lightning_rsa"
    ), patch("lightning_sdk.cli.utils.ssh_connection.subprocess.run") as run:
        result = CliRunner().invoke(ssh_job, ["train", "--teamspace", "org/teamspace"])

    assert result.exit_code == 0, result.output
    resolve_job.assert_called_once_with("train", teamspace)
    expected_cmd = [
        "ssh", "-i", "/tmp/lightning_rsa",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "StrictHostKeyChecking=no",
        "-o", "LogLevel=ERROR",
        "j_01jj4hvvjj4zx1t1esm5az3zt7@ssh.lightning.ai",
    ]
    run.assert_called_once_with(expected_cmd)


def test_ssh_selects_mmt_rank() -> None:
    mmt = MagicMock(spec=MMT)
    mmt.is_multi_machine = True
    machine = MagicMock()
    machine.name = "distributed-1"
    machine.status = Status.Running
    machine.id = "job_rank1"

    with patch("lightning_sdk.cli.job.ssh.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.job.ssh.resolve_job",
        return_value=mmt,
    ), patch(
        "lightning_sdk.cli.job.ssh.resolve_job_machine",
        return_value=machine,
    ) as resolve_rank, patch(
        "lightning_sdk.cli.utils.ssh_connection.configure_ssh_internal",
        return_value="/tmp/lightning_rsa",
    ), patch("lightning_sdk.cli.utils.ssh_connection.subprocess.run") as run:
        ssh_impl(name="distributed", teamspace=None, rank=1)

    resolve_rank.assert_called_once_with(mmt, 1)
    run.assert_called_once_with(
        ["ssh", "-i", "/tmp/lightning_rsa",
         "-o", "UserKnownHostsFile=/dev/null",
         "-o", "StrictHostKeyChecking=no",
         "-o", "LogLevel=ERROR",
         "j_rank1@ssh.lightning.ai"]
    )


def test_ssh_retries_with_fresh_keys_on_failure() -> None:
    job = MagicMock()
    job.name = "train"
    job.status = Status.Running
    job.id = "job_01abc"

    configure = MagicMock(side_effect=["/tmp/old_key", "/tmp/new_key"])
    run = MagicMock(side_effect=[OSError("ssh missing"), None])

    with patch("lightning_sdk.cli.job.ssh.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.job.ssh.resolve_job", return_value=job
    ), patch("lightning_sdk.cli.utils.ssh_connection.configure_ssh_internal", configure), patch(
        "lightning_sdk.cli.utils.ssh_connection.subprocess.run", run
    ):
        ssh_impl(name="train", teamspace=None)

    assert configure.call_count == 2
    configure.assert_any_call(force_download=True)
    assert run.call_args_list[0].args[0][2] == "/tmp/old_key"
    assert run.call_args_list[1].args[0][2] == "/tmp/new_key"
    assert run.call_args_list[1].args[0][-1] == "j_01abc@ssh.lightning.ai"
