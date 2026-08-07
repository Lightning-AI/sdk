from unittest.mock import MagicMock, patch

import pytest
import rich_click as click
from click.testing import CliRunner

from lightning_sdk.cli.mmt.ssh import _ssh_user_for_job_id, ssh_impl, ssh_mmt
from lightning_sdk.status import Status
from tests.cli.help import assert_help_contains, mock_command_logging


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
def test_mmt_ssh_help() -> None:
    assert_help_contains(
        "lightning mmt ssh --help",
        "Usage: lightning mmt ssh",
        "SSH into a running multi-machine job.",
        "--teamspace",
        "--rank",
    )


@mock_command_logging
def test_mmts_ssh_help() -> None:
    assert_help_contains(
        "lightning mmts ssh --help",
        "Usage: lightning mmts ssh",
        "SSH into a running multi-machine job.",
    )


def test_ssh_resolves_before_downloading_keys() -> None:
    configure = MagicMock()
    with patch(
        "lightning_sdk.cli.mmt.ssh.resolve_teamspace",
        return_value=MagicMock(name="coding-model-training"),
    ), patch(
        "lightning_sdk.cli.mmt.ssh.resolve_mmt",
        side_effect=click.UsageError("Could not resolve multi-machine job 'missing'."),
    ), patch(
        "lightning_sdk.cli.mmt.ssh.configure_ssh_internal",
        configure,
    ), pytest.raises(click.UsageError, match="Could not resolve multi-machine job"):
        ssh_impl(name="missing", teamspace=None)

    configure.assert_not_called()


def test_ssh_rejects_non_running_machine() -> None:
    rank0 = MagicMock()
    rank0.name = "train-0"
    rank0.rank = 0
    rank0.status = Status.Completed
    rank0.id = "job_01abc"

    mmt = MagicMock()
    mmt.name = "train"
    mmt.machines = (rank0,)

    with patch("lightning_sdk.cli.mmt.ssh.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.mmt.ssh.resolve_mmt", return_value=mmt
    ), patch("lightning_sdk.cli.mmt.ssh.configure_ssh_internal") as configure, pytest.raises(
        click.ClickException, match="not Running"
    ):
        ssh_impl(name="train", teamspace=None)

    configure.assert_not_called()


def test_ssh_defaults_to_rank_zero() -> None:
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

    with patch("lightning_sdk.cli.mmt.ssh.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.mmt.ssh.resolve_mmt", return_value=mmt
    ) as resolve_mmt, patch(
        "lightning_sdk.cli.mmt.ssh.configure_ssh_internal", return_value="/tmp/lightning_rsa"
    ), patch("lightning_sdk.cli.mmt.ssh.subprocess.run") as run:
        result = CliRunner().invoke(ssh_mmt, ["train", "--teamspace", "org/ts"])

    assert result.exit_code == 0, result.output
    resolve_mmt.assert_called_once_with("train", teamspace)
    run.assert_called_once_with(["ssh", "-i", "/tmp/lightning_rsa", "j_rank0@ssh.lightning.ai"])


def test_ssh_selects_requested_rank() -> None:
    teamspace = MagicMock()
    rank0 = MagicMock()
    rank0.name = "olmo3-7b-think-sft-full-0"
    rank0.rank = 0
    rank0.status = Status.Running
    rank0.id = "job_r0"

    rank1 = MagicMock()
    rank1.name = "olmo3-7b-think-sft-full-1"
    rank1.rank = 1
    rank1.status = Status.Running
    rank1.id = "job_r1"

    mmt = MagicMock()
    mmt.name = "olmo3-7b-think-sft-full"
    mmt.machines = (rank0, rank1)

    with patch("lightning_sdk.cli.mmt.ssh.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.mmt.ssh.resolve_mmt", return_value=mmt
    ), patch("lightning_sdk.cli.mmt.ssh.configure_ssh_internal", return_value="/tmp/lightning_rsa"), patch(
        "lightning_sdk.cli.mmt.ssh.subprocess.run"
    ) as run:
        result = CliRunner().invoke(ssh_mmt, ["olmo3-7b-think-sft-full", "--rank", "1"])

    assert result.exit_code == 0, result.output
    run.assert_called_once_with(["ssh", "-i", "/tmp/lightning_rsa", "j_r1@ssh.lightning.ai"])


def test_ssh_rejects_unknown_rank() -> None:
    rank0 = MagicMock()
    rank0.name = "train-0"
    rank0.rank = 0

    mmt = MagicMock()
    mmt.name = "train"
    mmt.machines = (rank0,)

    with patch("lightning_sdk.cli.mmt.ssh.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.mmt.ssh.resolve_mmt", return_value=mmt
    ), pytest.raises(click.ClickException, match="Rank 3 not found.*Available ranks: 0"):
        ssh_impl(name="train", teamspace=None, rank=3)


def test_ssh_selects_rank_when_names_lack_rank_suffix() -> None:
    """Machines are matched on their rank, not on a ``{job}-{rank}`` name convention."""
    rank0 = MagicMock()
    rank0.name = "worker-alpha"
    rank0.rank = 0
    rank0.status = Status.Running
    rank0.id = "job_r0"

    rank1 = MagicMock()
    rank1.name = "worker-beta"
    rank1.rank = 1
    rank1.status = Status.Running
    rank1.id = "job_r1"

    mmt = MagicMock()
    mmt.name = "train"
    mmt.machines = (rank0, rank1)

    with patch("lightning_sdk.cli.mmt.ssh.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.mmt.ssh.resolve_mmt", return_value=mmt
    ), patch("lightning_sdk.cli.mmt.ssh.configure_ssh_internal", return_value="/tmp/lightning_rsa"), patch(
        "lightning_sdk.cli.mmt.ssh.subprocess.run"
    ) as run:
        ssh_impl(name="train", teamspace=None, rank=1)

    run.assert_called_once_with(["ssh", "-i", "/tmp/lightning_rsa", "j_r1@ssh.lightning.ai"])


def test_ssh_retries_with_fresh_keys_on_failure() -> None:
    rank0 = MagicMock()
    rank0.name = "train-0"
    rank0.rank = 0
    rank0.status = Status.Running
    rank0.id = "job_01abc"

    mmt = MagicMock()
    mmt.name = "train"
    mmt.machines = (rank0,)

    configure = MagicMock(side_effect=["/tmp/old_key", "/tmp/new_key"])
    run = MagicMock(side_effect=[OSError("ssh missing"), None])

    with patch("lightning_sdk.cli.mmt.ssh.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.mmt.ssh.resolve_mmt", return_value=mmt
    ), patch("lightning_sdk.cli.mmt.ssh.configure_ssh_internal", configure), patch(
        "lightning_sdk.cli.mmt.ssh.subprocess.run", run
    ):
        ssh_impl(name="train", teamspace=None)

    assert configure.call_count == 2
    configure.assert_any_call(force_download=True)
    assert run.call_args_list[0].args[0][2] == "/tmp/old_key"
    assert run.call_args_list[1].args[0][2] == "/tmp/new_key"
    assert run.call_args_list[1].args[0][-1] == "j_01abc@ssh.lightning.ai"
