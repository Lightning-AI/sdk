from unittest.mock import MagicMock

from click.testing import CliRunner

from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_job_inspect_help() -> None:
    assert_help_contains(
        "lightning job inspect --help",
        "Usage: lightning job inspect",
        "Inspect a job for further details as JSON.",
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
def test_job_inspect_uses_positional_name(monkeypatch) -> None:
    from lightning_sdk.cli.job.inspect import inspect_job

    captured = {}
    job = MagicMock()
    job.json.return_value = '{"name":"my-job"}'

    class _FakeJobAndMMTAction:
        def job(self, name=None, teamspace=None):
            captured["name"] = name
            captured["teamspace"] = teamspace
            return job

    monkeypatch.setattr("lightning_sdk.cli.job.inspect._JobAndMMTAction", _FakeJobAndMMTAction)

    runner = CliRunner()
    result = runner.invoke(inspect_job, ["my-job", "--teamspace", "org/teamspace"])

    assert result.exit_code == 0
    assert captured == {"name": "my-job", "teamspace": "org/teamspace"}
    assert '{"name":"my-job"}' in result.output


@mock_command_logging
def test_job_inspect_help_shows_positional_name() -> None:
    assert_help_contains("lightning job inspect --help", "Usage: lightning job inspect [OPTIONS] [NAME]")
