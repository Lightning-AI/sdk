from unittest.mock import MagicMock, patch

import rich_click as click
from click.testing import CliRunner

from lightning_sdk.cli.job import register_commands
from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_job_delete_help() -> None:
    text = assert_help_contains(
        "lightning job delete --help",
        "Usage: lightning job delete [OPTIONS] NAME",
        "Delete a job.",
        "--yes",
        "-y",
    )
    assert "--json" not in text


def test_delete_job_uses_shared_command() -> None:
    resource = MagicMock()
    with patch("lightning_sdk.job.Job", return_value=resource) as job_cls:
        group = click.Group()
        register_commands(group)
        result = CliRunner().invoke(group, ["delete", "my-job", "-y"])

    assert result.exit_code == 0
    assert result.output == "Job deleted\n"
    job_cls.assert_called_once_with(name="my-job", teamspace=None)
    resource.delete.assert_called_once_with()


@mock_command_logging
def test_jobs_delete_help() -> None:
    assert_help_contains(
        "lightning jobs delete --help",
        "Usage: lightning jobs delete [OPTIONS] NAME",
        "Delete a job.",
        "--yes",
        "-y",
    )


@mock_command_logging
def test_delete_help() -> None:
    text = assert_help_contains(
        "lightning delete --help",
        "`lightning delete` has moved to noun-first commands:",
        "container -> lightning container delete",
        "job -> lightning job delete",
        "mmt -> lightning mmt delete",
        "studio -> lightning studio delete",
    )
    assert "Deprecation warning:" not in text


@mock_command_logging
def test_delete_job_legacy_help() -> None:
    assert_help_contains(
        "lightning delete job --help",
        "Deprecation warning:",
        "Use `lightning job delete` instead of `lightning delete job`.",
        "Usage: lightning delete job [OPTIONS] NAME",
        "--yes",
        "-y",
    )
