from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from lightning_sdk.cli.job.tag import tag_job
from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_job_tag_help() -> None:
    assert_help_contains(
        "lightning job tag --help",
        "Usage: lightning job tag",
        "Add tags to a job.",
        "--teamspace",
        "--json",
    )


@mock_command_logging
def test_tag_job_adds_tags() -> None:
    teamspace = MagicMock()
    job = MagicMock()
    job.name = "my-job"
    job.tags = ["prod", "gpu"]
    with patch("lightning_sdk.cli.job.tag.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.tag.resolve_job", return_value=job
    ):
        result = CliRunner().invoke(tag_job, ["my-job", "prod", "gpu", "--teamspace", "org/ts"])

    assert result.exit_code == 0
    assert "Tags set on 'my-job': prod, gpu" in result.output
    assert job.add_tag.call_count == 2
    job.add_tag.assert_any_call("prod")
    job.add_tag.assert_any_call("gpu")


@mock_command_logging
def test_tag_job_json_output() -> None:
    teamspace = MagicMock()
    job = MagicMock()
    job.name = "my-job"
    job.tags = ["prod"]
    with patch("lightning_sdk.cli.job.tag.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.tag.resolve_job", return_value=job
    ):
        result = CliRunner().invoke(tag_job, ["my-job", "prod", "--json"])

    assert result.exit_code == 0
    assert '"name": "my-job"' in result.output
    assert '"prod"' in result.output
