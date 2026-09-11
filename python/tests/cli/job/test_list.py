import io
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from rich.console import Console

from lightning_sdk.cli.job.list import list_jobs
from lightning_sdk.cli.legacy.list import jobs
from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_job_list_help() -> None:
    text = assert_help_contains(
        "lightning job list --help",
        "Usage: lightning job list",
        "List jobs for a given teamspace.",
    )
    normalized_text = " ".join(text.replace("│", " ").split())
    assert "Defaults to the configured teamspace." in normalized_text
    assert "interactive menu" not in normalized_text


@mock_command_logging
def test_jobs_list_help() -> None:
    assert_help_contains("lightning jobs list --help", "Usage: lightning jobs list", "List jobs for a given teamspace.")


def _teamspace_with_jobs() -> SimpleNamespace:
    """Build a teamspace whose jobs expose only the attributes real Job/MMT objects have."""
    owner = SimpleNamespace(name="org")
    teamspace = SimpleNamespace(name="teamspace", owner=owner)
    single = SimpleNamespace(
        name="single",
        teamspace=teamspace,
        studio_name=None,
        image="ubuntu",
        status="Running",
        machine="CPU",
        started_at=datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
        stopped_at=datetime(2026, 8, 1, 13, 0, tzinfo=timezone.utc),
        total_cost=1.0,
        tags=("prod", "team a"),
    )
    multi = SimpleNamespace(
        name="distributed",
        teamspace=teamspace,
        studio_name=None,
        image="ubuntu",
        status="Running",
        machine="CPU",
        num_machines=4,
        started_at=datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc),
        stopped_at=None,
        total_cost=4.0,
        tags=(),
    )
    teamspace.list_jobs = MagicMock(return_value=[single, multi])
    teamspace.multi_machine_jobs = [multi]
    return teamspace


@mock_command_logging
def test_job_list_includes_single_and_multi_machine_jobs() -> None:
    teamspace = _teamspace_with_jobs()

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace):
        result = CliRunner().invoke(list_jobs, ["--json"])

    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert [(row["name"], row["num_machines"]) for row in rows] == [
        ("distributed", 4),
        ("single", 1),
    ]


@mock_command_logging
def test_job_list_includes_and_sorts_by_timestamps() -> None:
    teamspace = _teamspace_with_jobs()

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace):
        result = CliRunner().invoke(list_jobs, ["--sort-by", "started", "--json"])

    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert [row["name"] for row in rows] == ["single", "distributed"]
    assert rows[0]["started_at"] == "2026-08-01T12:00:00+00:00"
    assert rows[0]["stopped_at"] == "2026-08-01T13:00:00+00:00"
    assert rows[1]["stopped_at"] is None


@mock_command_logging
def test_job_list_sort_by_stopped_puts_unfinished_first() -> None:
    teamspace = _teamspace_with_jobs()

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace):
        result = CliRunner().invoke(list_jobs, ["--sort-by", "stopped", "--json"])

    assert result.exit_code == 0, result.output
    assert [row["name"] for row in json.loads(result.output)] == ["distributed", "single"]


@mock_command_logging
def test_job_list_sort_by_cloud_account_without_attribute() -> None:
    teamspace = _teamspace_with_jobs()

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace):
        result = CliRunner().invoke(list_jobs, ["--sort-by", "cloud-account", "--json"])

    assert result.exit_code == 0, result.output
    assert {row["name"] for row in json.loads(result.output)} == {"single", "distributed"}


@mock_command_logging
def test_list_jobs_legacy_help() -> None:
    assert_help_contains(
        "lightning list jobs --help",
        "Deprecation warning:",
        "Use `lightning job list` instead of `lightning list jobs`.",
        "Usage: lightning list jobs [OPTIONS]",
    )
    result = CliRunner().invoke(jobs, ["--help"])
    assert result.exit_code == 0
    normalized_text = " ".join(result.output.replace("│", " ").split())
    assert "Should be specified as {owner}/{name}. Defaults to the current teamspace." in normalized_text


@mock_command_logging
def test_job_list_passes_no_tag_filter_by_default() -> None:
    teamspace = _teamspace_with_jobs()

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace):
        result = CliRunner().invoke(list_jobs, ["--json"])

    assert result.exit_code == 0, result.output
    teamspace.list_jobs.assert_called_once_with(tags=[])


@mock_command_logging
def test_job_list_filters_by_comma_separated_and_repeated_tags() -> None:
    teamspace = _teamspace_with_jobs()

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace):
        result = CliRunner().invoke(list_jobs, ["--tags", "prod,team a", "--tag", "staging", "--json"])

    assert result.exit_code == 0, result.output
    teamspace.list_jobs.assert_called_once_with(tags=["prod", "team a", "staging"])


@mock_command_logging
def test_job_list_filters_every_teamspace_with_all() -> None:
    first, second = _teamspace_with_jobs(), _teamspace_with_jobs()

    with patch("lightning_sdk.cli.job.list._list_teamspaces", return_value=["org/first", "org/second"]), patch(
        "lightning_sdk.cli.job.list.resolve_teamspace", side_effect=[first, second]
    ):
        result = CliRunner().invoke(list_jobs, ["--all", "--tags", "prod", "--json"])

    assert result.exit_code == 0, result.output
    first.list_jobs.assert_called_once_with(tags=["prod"])
    second.list_jobs.assert_called_once_with(tags=["prod"])


@mock_command_logging
def test_job_list_json_includes_tags() -> None:
    teamspace = _teamspace_with_jobs()

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace):
        result = CliRunner().invoke(list_jobs, ["--json"])

    assert result.exit_code == 0, result.output
    assert {row["name"]: row["tags"] for row in json.loads(result.output)} == {
        "single": ["prod", "team a"],
        "distributed": [],
    }


@mock_command_logging
def test_job_list_table_shows_tags() -> None:
    teamspace = _teamspace_with_jobs()
    # Wide enough that rich never wraps a cell, so each job stays on one line.
    console = Console(file=io.StringIO(), width=400)

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.list.Console", return_value=console
    ):
        result = CliRunner().invoke(list_jobs, [])

    assert result.exit_code == 0, result.output
    lines = console.file.getvalue().splitlines()
    assert "Tags" in next(line for line in lines if "Name" in line)
    assert "prod, team a" in next(line for line in lines if "single" in line)
