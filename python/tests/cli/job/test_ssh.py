from unittest.mock import MagicMock, patch

import pytest
import rich_click as click
from click.testing import CliRunner

from lightning_sdk.cli.job.ssh import _ssh_user_for_job_id, ssh_impl, ssh_job
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
    assert _ssh_user_for_job_id(job_id) == expected


@mock_command_logging
def test_job_ssh_help() -> None:
    result_text = command_text("lightning job ssh --help")

    assert "Usage: lightning job ssh [OPTIONS] NAME" in result_text
    assert "SSH into a running job." in result_text
    assert "--teamspace" in result_text
    assert "--rank" in result_text
    assert "--option" not in result_text


@mock_command_logging
def test_jobs_ssh_help() -> None:
    assert_help_contains("lightning jobs ssh --help", "Usage: lightning jobs ssh", "SSH into a running job.")


def test_ssh_resolves_before_downloading_keys() -> None:
    """SSH lookup failures occur before key downloads."""
    configure = MagicMock()
    with patch(
        "lightning_sdk.cli.job.ssh.resolve_teamspace",
        return_value=MagicMock(name="coding-model-training"),
    ), patch(
        "lightning_sdk.cli.job.ssh.resolve_job",
        side_effect=click.UsageError("Could not resolve job 'missing'."),
    ), patch(
        "lightning_sdk.cli.job.ssh.resolve_mmt",
        side_effect=click.UsageError("Could not resolve multi-machine job 'missing'."),
    ), patch(
        "lightning_sdk.cli.job.ssh.configure_ssh_internal",
        configure,
    ), pytest.raises(click.ClickException, match="Could not resolve job or multi-machine job"):
        ssh_impl(name="missing", teamspace=None)

    configure.assert_not_called()


def test_ssh_rejects_non_running_job() -> None:
    job = MagicMock()
    job.name = "train"
    job.status = Status.Completed
    job.id = "job_01abc"

    with patch("lightning_sdk.cli.job.ssh.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.job.ssh.resolve_job", return_value=job
    ), patch("lightning_sdk.cli.job.ssh.configure_ssh_internal") as configure, pytest.raises(
        click.ClickException, match="not Running"
    ):
        ssh_impl(name="train", teamspace=None)

    configure.assert_not_called()


def test_ssh_runs_against_job_gateway_user() -> None:
    teamspace = MagicMock()
    job = MagicMock()
    job.name = "train"
    job.status = Status.Running
    job.id = "job_01jj4hvvjj4zx1t1esm5az3zt7"

    with patch("lightning_sdk.cli.job.ssh.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.ssh.resolve_job", return_value=job
    ) as resolve_job, patch(
        "lightning_sdk.cli.job.ssh.configure_ssh_internal", return_value="/tmp/lightning_rsa"
    ), patch("lightning_sdk.cli.job.ssh.subprocess.run") as run:
        result = CliRunner().invoke(ssh_job, ["train", "--teamspace", "org/teamspace"])

    assert result.exit_code == 0, result.output
    resolve_job.assert_called_once_with("train", teamspace)
    run.assert_called_once_with(["ssh", "-i", "/tmp/lightning_rsa", "j_01jj4hvvjj4zx1t1esm5az3zt7@ssh.lightning.ai"])


def test_ssh_retries_with_fresh_keys_on_failure() -> None:
    job = MagicMock()
    job.name = "train"
    job.status = Status.Running
    job.id = "job_01abc"

    configure = MagicMock(side_effect=["/tmp/old_key", "/tmp/new_key"])
    run = MagicMock(side_effect=[OSError("ssh missing"), None])

    with patch("lightning_sdk.cli.job.ssh.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.job.ssh.resolve_job", return_value=job
    ), patch("lightning_sdk.cli.job.ssh.configure_ssh_internal", configure), patch(
        "lightning_sdk.cli.job.ssh.subprocess.run", run
    ):
        ssh_impl(name="train", teamspace=None)

    assert configure.call_count == 2
    configure.assert_any_call(force_download=True)
    assert run.call_args_list[0].args[0][2] == "/tmp/old_key"
    assert run.call_args_list[1].args[0][2] == "/tmp/new_key"
    assert run.call_args_list[1].args[0][-1] == "j_01abc@ssh.lightning.ai"


def test_ssh_falls_back_to_mmt_rank() -> None:
    teamspace = MagicMock()
    rank0 = MagicMock()
    rank0.name = "train-0"
    rank0.rank = 0
    rank0.status = Status.Running
    rank0.id = "job_rank0"

    rank1 = MagicMock()
    rank1.name = "train-1"
    rank1.rank = 1
    rank1.status = Status.Running
    rank1.id = "job_rank1"

    mmt = MagicMock()
    mmt.name = "train"
    mmt.machines = (rank0, rank1)

    with patch("lightning_sdk.cli.job.ssh.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.ssh.resolve_job",
        side_effect=click.UsageError("no job"),
    ), patch(
        "lightning_sdk.cli.job.ssh.resolve_mmt",
        return_value=mmt,
    ) as resolve_mmt, patch(
        "lightning_sdk.cli.job.ssh.configure_ssh_internal", return_value="/tmp/lightning_rsa"
    ), patch("lightning_sdk.cli.job.ssh.subprocess.run") as run:
        result = CliRunner().invoke(ssh_job, ["train", "--rank", "1", "--teamspace", "org/ts"])

    assert result.exit_code == 0, result.output
    resolve_mmt.assert_called_once_with("train", teamspace)
    run.assert_called_once_with(["ssh", "-i", "/tmp/lightning_rsa", "j_rank1@ssh.lightning.ai"])


def test_ssh_mmt_rank_uses_name_suffix_when_spec_rank_is_wrong() -> None:
    teamspace = MagicMock()
    rank0 = MagicMock()
    rank0.name = "olmo3-7b-think-sft-full-0"
    rank0.rank = 0
    rank0.status = Status.Running
    rank0.id = "job_r0"

    rank1 = MagicMock()
    rank1.name = "olmo3-7b-think-sft-full-1"
    rank1.rank = 0
    rank1.status = Status.Running
    rank1.id = "job_r1"

    mmt = MagicMock()
    mmt.name = "olmo3-7b-think-sft-full"
    mmt.machines = (rank0, rank1)

    with patch("lightning_sdk.cli.job.ssh.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.ssh.resolve_job",
        side_effect=click.UsageError("no job"),
    ), patch(
        "lightning_sdk.cli.job.ssh.resolve_mmt",
        return_value=mmt,
    ), patch("lightning_sdk.cli.job.ssh.configure_ssh_internal", return_value="/tmp/lightning_rsa"), patch(
        "lightning_sdk.cli.job.ssh.subprocess.run"
    ) as run:
        result = CliRunner().invoke(ssh_job, ["olmo3-7b-think-sft-full", "--rank", "1"])

    assert result.exit_code == 0, result.output
    run.assert_called_once_with(["ssh", "-i", "/tmp/lightning_rsa", "j_r1@ssh.lightning.ai"])


def test_ssh_warns_when_rank_ignored_for_single_job() -> None:
    job = MagicMock()
    job.name = "train-0"
    job.status = Status.Running
    job.id = "job_01abc"

    with patch("lightning_sdk.cli.job.ssh.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.job.ssh.resolve_job", return_value=job
    ), patch("lightning_sdk.cli.job.ssh.configure_ssh_internal", return_value="/tmp/lightning_rsa"), patch(
        "lightning_sdk.cli.job.ssh.subprocess.run"
    ), patch("lightning_sdk.cli.job.ssh.click.echo") as echo:
        ssh_impl(name="train-0", teamspace=None, rank=1)

    echo.assert_called_once()
    assert "ignoring --rank 1" in echo.call_args.args[0]


def test_ssh_mmt_defaults_to_rank_zero() -> None:
    teamspace = MagicMock()
    rank0 = MagicMock()
    rank0.name = "train-0"
    rank0.rank = 0
    rank0.status = Status.Running
    rank0.id = "job_rank0"

    mmt = MagicMock()
    mmt.name = "train"
    mmt.machines = (rank0,)

    with patch("lightning_sdk.cli.job.ssh.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.ssh.resolve_job",
        side_effect=click.UsageError("no job"),
    ), patch(
        "lightning_sdk.cli.job.ssh.resolve_mmt",
        return_value=mmt,
    ), patch("lightning_sdk.cli.job.ssh.configure_ssh_internal", return_value="/tmp/lightning_rsa"), patch(
        "lightning_sdk.cli.job.ssh.subprocess.run"
    ) as run:
        ssh_impl(name="train", teamspace="org/ts")

    run.assert_called_once_with(["ssh", "-i", "/tmp/lightning_rsa", "j_rank0@ssh.lightning.ai"])


def test_ssh_mmt_rejects_unknown_rank() -> None:
    teamspace = MagicMock()
    rank0 = MagicMock()
    rank0.rank = 0

    mmt = MagicMock()
    mmt.name = "train"
    mmt.machines = (rank0,)

    with patch("lightning_sdk.cli.job.ssh.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.ssh.resolve_job",
        side_effect=click.UsageError("no job"),
    ), patch(
        "lightning_sdk.cli.job.ssh.resolve_mmt",
        return_value=mmt,
    ), pytest.raises(click.ClickException, match="Rank 3 not found"):
        ssh_impl(name="train", teamspace=None, rank=3)
