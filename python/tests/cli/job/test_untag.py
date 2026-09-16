from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from lightning_sdk.cli.job.untag import untag_job
from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_job_untag_help() -> None:
    assert_help_contains(
        "lightning job untag --help",
        "Usage: lightning job untag",
        "Remove tags from a job.",
        "--teamspace",
        "--json",
    )


@mock_command_logging
def test_untag_job_removes_tags() -> None:
    teamspace = MagicMock()
    job = MagicMock()
    job.name = "my-job"
    job.tags = ["gpu"]
    with patch("lightning_sdk.cli.job.untag.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.untag.resolve_job", return_value=job
    ):
        result = CliRunner().invoke(untag_job, ["my-job", "prod", "--teamspace", "org/ts"])

    assert result.exit_code == 0
    assert "Tags on 'my-job': gpu" in result.output
    job.remove_tag.assert_called_once_with("prod")


@mock_command_logging
def test_untag_job_all_removed() -> None:
    teamspace = MagicMock()
    job = MagicMock()
    job.name = "my-job"
    job.tags = []
    with patch("lightning_sdk.cli.job.untag.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.untag.resolve_job", return_value=job
    ):
        result = CliRunner().invoke(untag_job, ["my-job", "prod"])

    assert result.exit_code == 0
    assert "All tags removed from 'my-job'" in result.output


@mock_command_logging
def test_untag_job_json_output() -> None:
    teamspace = MagicMock()
    job = MagicMock()
    job.name = "my-job"
    job.tags = []
    with patch("lightning_sdk.cli.job.untag.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.untag.resolve_job", return_value=job
    ):
        result = CliRunner().invoke(untag_job, ["my-job", "prod", "--json"])

    assert result.exit_code == 0
    assert '"name": "my-job"' in result.output
    assert '"tags"' in result.output
