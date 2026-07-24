from unittest.mock import MagicMock

from click.testing import CliRunner

from lightning_sdk.status import Status
from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_job_logs_help() -> None:
    assert_help_contains(
        "lightning job logs --help",
        "Usage: lightning job logs",
        "Print the logs for a job.",
    )


@mock_command_logging
def test_jobs_logs_help() -> None:
    assert_help_contains(
        "lightning jobs logs --help",
        "Usage: lightning jobs logs",
        "Print the logs for a job.",
    )


@mock_command_logging
def test_job_logs_help_shows_positional_name() -> None:
    assert_help_contains("lightning job logs --help", "Usage: lightning job logs [OPTIONS] [NAME]")


def _patch_action(monkeypatch, job: MagicMock, captured: dict) -> None:
    class _FakeJobAndMMTAction:
        def job(self, name=None, teamspace=None):
            captured["name"] = name
            captured["teamspace"] = teamspace
            return job

    monkeypatch.setattr("lightning_sdk.cli.job.logs._JobAndMMTAction", _FakeJobAndMMTAction)


@mock_command_logging
def test_job_logs_prints_logs_when_terminal(monkeypatch) -> None:
    from lightning_sdk.cli.job.logs import logs_job

    captured: dict = {}
    job = MagicMock()
    job.name = "my-job"
    job.status = Status.Completed
    job.logs = "hello from the job\n42"
    _patch_action(monkeypatch, job, captured)

    result = CliRunner().invoke(logs_job, ["my-job", "--teamspace", "org/teamspace"])

    assert result.exit_code == 0
    assert captured == {"name": "my-job", "teamspace": "org/teamspace"}
    assert "hello from the job" in result.output
    assert "42" in result.output


@mock_command_logging
def test_job_logs_errors_while_not_terminal(monkeypatch) -> None:
    from lightning_sdk.cli.job.logs import logs_job

    captured: dict = {}
    job = MagicMock()
    job.name = "my-job"
    job.status = Status.Pending
    _patch_action(monkeypatch, job, captured)

    result = CliRunner().invoke(logs_job, ["my-job", "--teamspace", "org/teamspace"])

    # errors cleanly (mentioning the status) rather than raising the raw SDK RuntimeError
    assert result.exit_code != 0
    assert "Pending" in result.output
    assert not isinstance(result.exception, RuntimeError)
