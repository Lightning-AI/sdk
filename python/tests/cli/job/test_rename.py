from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from lightning_sdk.cli.job.rename import rename_job
from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_job_rename_help() -> None:
    assert_help_contains(
        "lightning job rename --help",
        "Usage: lightning job rename",
        "Rename a job.",
        "--teamspace",
        "--json",
    )


@mock_command_logging
def test_rename_job_resolves_and_renames() -> None:
    teamspace = MagicMock()
    job = MagicMock()
    job.name = "new-name"
    with patch("lightning_sdk.cli.job.rename.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.rename.resolve_job", return_value=job
    ):
        result = CliRunner().invoke(rename_job, ["old-name", "new-name", "--teamspace", "org/ts"])

    assert result.exit_code == 0
    assert "Successfully renamed job to 'new-name'!" in result.output
    job.rename.assert_called_once_with("new-name")


@mock_command_logging
def test_rename_job_json_output() -> None:
    teamspace = MagicMock()
    job = MagicMock()
    job.name = "new-name"
    with patch("lightning_sdk.cli.job.rename.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.rename.resolve_job", return_value=job
    ):
        result = CliRunner().invoke(rename_job, ["old-name", "new-name", "--json"])

    assert result.exit_code == 0
    assert '"name": "new-name"' in result.output
    assert '"status": "renamed"' in result.output
