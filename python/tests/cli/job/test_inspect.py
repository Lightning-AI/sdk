from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from lightning_sdk.mmt import MMT
from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_job_inspect_help() -> None:
    assert_help_contains(
        "lightning job inspect --help",
        "Usage: lightning job inspect",
        "Inspect a job for further details as JSON.",
        "configured default teamspace",
    )


@mock_command_logging
def test_jobs_inspect_help() -> None:
    assert_help_contains(
        "lightning jobs inspect --help",
        "Usage: lightning jobs inspect",
        "Inspect a job for further details as JSON.",
    )


@mock_command_logging
def test_inspect_help() -> None:
    text = assert_help_contains(
        "lightning inspect --help",
        "`lightning inspect` has moved to noun-first commands:",
        "job -> lightning job inspect",
        "mmt -> lightning mmt inspect",
    )
    assert "Deprecation warning:" not in text


@mock_command_logging
def test_inspect_job_legacy_help() -> None:
    assert_help_contains(
        "lightning inspect job --help",
        "Deprecation warning:",
        "Use `lightning job inspect` instead of `lightning inspect job`.",
        "Usage: lightning inspect job [OPTIONS] [NAME]",
    )


@mock_command_logging
def test_job_inspect_uses_positional_name() -> None:
    from lightning_sdk.cli.job.inspect import inspect_job

    teamspace = MagicMock()
    job = MagicMock()
    job.json.return_value = '{"name":"my-job"}'

    with patch("lightning_sdk.cli.job.inspect.resolve_teamspace", return_value=teamspace) as resolve_teamspace, patch(
        "lightning_sdk.cli.job.inspect.resolve_job", return_value=job
    ) as resolve_job:
        result = CliRunner().invoke(inspect_job, ["my-job", "--teamspace", "org/teamspace"])

    assert result.exit_code == 0
    resolve_teamspace.assert_called_once_with("org/teamspace")
    resolve_job.assert_called_once_with("my-job", teamspace)
    assert '{"name":"my-job"}' in result.output
    job.json.assert_called_once_with()


@mock_command_logging
def test_job_inspect_selects_mmt_rank() -> None:
    from lightning_sdk.cli.job.inspect import inspect_job

    teamspace = MagicMock()
    mmt = MagicMock(spec=MMT)
    mmt.is_multi_machine = True
    machine = MagicMock()
    machine.json.return_value = '{"name":"distributed-1"}'
    with patch("lightning_sdk.cli.job.inspect.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.inspect.resolve_job",
        return_value=mmt,
    ), patch(
        "lightning_sdk.cli.job.inspect.resolve_job_machine",
        return_value=machine,
    ) as resolve_rank:
        result = CliRunner().invoke(inspect_job, ["distributed", "--rank", "1"])

    assert result.exit_code == 0
    resolve_rank.assert_called_once_with(mmt, 1)
    assert "distributed-1" in result.output


@mock_command_logging
def test_job_inspect_help_shows_positional_name() -> None:
    assert_help_contains("lightning job inspect --help", "Usage: lightning job inspect [OPTIONS] [NAME]")


@mock_command_logging
def test_job_inspect_requires_name_without_listing_resources() -> None:
    from lightning_sdk.cli.job.inspect import inspect_job

    teamspace = MagicMock()
    with patch("lightning_sdk.cli.job.inspect.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.utils.resource_resolution.Job"
    ) as job:
        result = CliRunner().invoke(inspect_job)

    assert result.exit_code != 0
    assert "Missing job name. Pass JOB." in result.output
    job.assert_not_called()
    assert teamspace.mock_calls == []
