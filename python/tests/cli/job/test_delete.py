from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_job_delete_help() -> None:
    assert_help_contains("lightning job delete --help", "Usage: lightning job delete", "Delete a job.")


@mock_command_logging
def test_jobs_delete_help() -> None:
    assert_help_contains("lightning jobs delete --help", "Usage: lightning jobs delete", "Delete a job.")


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
    )


@mock_command_logging
def test_job_delete_resolves_exact_name() -> None:
    from lightning_sdk.cli.job.delete import delete_job

    teamspace = MagicMock()
    job = MagicMock()
    job.name = "train"
    with patch("lightning_sdk.cli.job.delete.resolve_teamspace", return_value=teamspace) as resolve_teamspace, patch(
        "lightning_sdk.cli.job.delete.resolve_job", return_value=job
    ) as resolve_job:
        result = CliRunner().invoke(delete_job, ["train", "--teamspace", "org/teamspace"])

    assert result.exit_code == 0
    resolve_teamspace.assert_called_once_with("org/teamspace")
    resolve_job.assert_called_once_with("train", teamspace)
    job.delete.assert_called_once_with()
