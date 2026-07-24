from unittest.mock import MagicMock

from click.testing import CliRunner

from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_job_logs_help() -> None:
    assert_help_contains(
        "lightning job logs --help",
        "Usage: lightning job logs",
        "Print the logs for a job.",
        "--follow",
        "--tail",
        "--rank",
        "--timestamps",
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
def test_job_logs_prints_snapshot(monkeypatch) -> None:
    from lightning_sdk.cli.job.logs import logs_job

    captured: dict = {}
    job = MagicMock()
    job.logs.return_value = "hello from the job\n42"
    _patch_action(monkeypatch, job, captured)

    result = CliRunner().invoke(logs_job, ["my-job", "--teamspace", "org/teamspace"])

    assert result.exit_code == 0
    assert captured == {"name": "my-job", "teamspace": "org/teamspace"}
    assert "hello from the job" in result.output
    assert "42" in result.output
    job.logs.assert_called_once_with(follow=False, tail=None, rank=None, timestamps=False)


@mock_command_logging
def test_job_logs_follows_with_options(monkeypatch) -> None:
    from lightning_sdk.cli.job.logs import logs_job

    captured: dict = {}
    job = MagicMock()
    job.logs.return_value = iter(["line 1", "line 2"])
    _patch_action(monkeypatch, job, captured)

    result = CliRunner().invoke(
        logs_job,
        ["my-job", "--follow", "--tail", "10", "--rank", "2", "--timestamps"],
    )

    assert result.exit_code == 0
    assert result.output == "line 1\nline 2\n"
    job.logs.assert_called_once_with(follow=True, tail=10, rank=2, timestamps=True)


@mock_command_logging
def test_job_logs_reports_sdk_errors_cleanly(monkeypatch) -> None:
    from lightning_sdk.cli.job.logs import logs_job

    captured: dict = {}
    job = MagicMock()
    job.logs.side_effect = RuntimeError("Logs are not available while the job is Pending.")
    _patch_action(monkeypatch, job, captured)

    result = CliRunner().invoke(logs_job, ["my-job"])

    assert result.exit_code != 0
    assert "Pending" in result.output
    assert not isinstance(result.exception, RuntimeError)
