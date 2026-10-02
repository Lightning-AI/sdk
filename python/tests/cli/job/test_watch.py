from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_job_watch_help() -> None:
    assert_help_contains(
        "lightning job watch --help",
        "Usage: lightning job watch",
        "Follow a job's progress live",
        "--json",
        "--state-dir",
        "--relaunch-wait",
    )


@mock_command_logging
def test_job_watch_runs_the_watcher_and_exits_with_its_code(tmp_path) -> None:
    from lightning_sdk.cli.job.watch import watch_job

    teamspace = MagicMock(id="ts-id")
    teamspace.name = "ts"
    teamspace.owner.name = "org"
    job = MagicMock()
    with patch("lightning_sdk.cli.job.watch.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.watch.resolve_job", return_value=job
    ) as resolve_job, patch("lightning_sdk.utils.job_progress.watch.JobWatcher") as watcher_cls:
        watcher_cls.return_value.watch.return_value = 1
        result = CliRunner().invoke(
            watch_job,
            ["train", "--teamspace", "org/ts", "--json", "--state-dir", str(tmp_path), "--relaunch-wait", "60"],
        )

    assert result.exit_code == 1
    resolve_job.assert_called_once_with("train", teamspace)
    kwargs = watcher_cls.call_args.kwargs
    assert watcher_cls.call_args.args == ("train",)
    assert (kwargs["teamspace"], kwargs["teamspace_id"]) == ("org/ts", "ts-id")
    assert kwargs["state_dir"] == tmp_path
    assert kwargs["relaunch_wait"] == 60
    assert type(kwargs["output"]).__name__ == "JsonLinesOutput"
    assert kwargs["job_factory"]("train", "org/ts") is job
