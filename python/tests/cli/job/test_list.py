import io
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest
from click.testing import CliRunner
from rich.console import Console

from lightning_sdk.cli.job.list import LIST_KEYS, _resolve_filters, list_jobs
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


def _teamspace_with_jobs(teamspace_id: str = "ts-id") -> SimpleNamespace:
    """Build a teamspace whose jobs expose only the attributes real Job/MMT objects have."""
    owner = SimpleNamespace(name="org")
    teamspace = SimpleNamespace(name="teamspace", owner=owner, id=teamspace_id)
    single = SimpleNamespace(
        name="single",
        teamspace=teamspace,
        _job=SimpleNamespace(user_id="user-1"),
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
        _job=SimpleNamespace(user_id="user-2"),
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


@pytest.fixture(autouse=True)
def creators():
    """Stub the one API call that turns job user ids into creator names."""
    with patch("lightning_sdk.cli.job.list.TeamspaceApi") as api:
        api.return_value.list_member_usernames.return_value = {"user-1": "justus", "user-2": "ada"}
        yield api.return_value.list_member_usernames


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


@mock_command_logging
def test_job_list_includes_creator() -> None:
    teamspace = _teamspace_with_jobs()

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace):
        result = CliRunner().invoke(list_jobs, ["--json"])

    assert result.exit_code == 0, result.output
    assert {row["name"]: row["creator"] for row in json.loads(result.output)} == {
        "single": "justus",
        "distributed": "ada",
    }


@mock_command_logging
def test_job_list_resolves_creators_once_per_teamspace(creators) -> None:
    """Creator names cost one membership lookup per teamspace, not one per job."""
    first, second = _teamspace_with_jobs("ts-1"), _teamspace_with_jobs("ts-2")

    with patch("lightning_sdk.cli.job.list._list_teamspaces", return_value=["org/first", "org/second"]), patch(
        "lightning_sdk.cli.job.list.resolve_teamspace", side_effect=[first, second]
    ):
        result = CliRunner().invoke(list_jobs, ["--all", "--json"])

    assert result.exit_code == 0, result.output
    assert len(json.loads(result.output)) == 4, "two jobs from each of the two teamspaces"
    assert creators.call_args_list == [call(teamspace_id="ts-1"), call(teamspace_id="ts-2")]


@mock_command_logging
def test_job_list_creator_falls_back_to_user_id_when_unresolvable(creators) -> None:
    teamspace = _teamspace_with_jobs()
    creators.side_effect = RuntimeError("no access to members")

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace):
        result = CliRunner().invoke(list_jobs, ["--json"])

    assert result.exit_code == 0, result.output
    # The warning goes to stderr, so --json output stays machine-readable.
    assert {row["creator"] for row in json.loads(result.stdout)} == {"user-1", "user-2"}
    assert "could not resolve creator names in org/teamspace" in result.stderr
    assert "no access to members" in result.stderr


@mock_command_logging
def test_job_list_sorts_by_creator() -> None:
    teamspace = _teamspace_with_jobs()

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace):
        result = CliRunner().invoke(list_jobs, ["--sort-by", "creator", "--json"])

    assert result.exit_code == 0, result.output
    assert [row["name"] for row in json.loads(result.output)] == ["distributed", "single"]


@mock_command_logging
def test_job_list_filters_on_a_real_value_for_every_key() -> None:
    """Every key `--sort-by` offers reads a field a job row actually has.

    `LIST_KEYS` feeding both options only keeps the names in parity; a key whose row field is
    missing or misspelled still parses, and then silently matches an empty value for every job.
    """
    teamspace = _teamspace_with_jobs()
    teamspace.list_jobs = MagicMock(
        return_value=[
            SimpleNamespace(
                name="full",
                teamspace=teamspace,
                _job=SimpleNamespace(user_id="user-1"),
                studio_name="my-studio",
                image="ubuntu",
                status="Running",
                machine="A100",
                cloud_account="my-account",
                num_machines=1,
                started_at=datetime(2026, 8, 3, 9, 30, tzinfo=timezone.utc),
                stopped_at=datetime(2026, 8, 3, 10, 30, tzinfo=timezone.utc),
                total_cost=2.0,
                tags=(),
            )
        ]
    )
    patterns = {
        "name": "full",
        "teamspace": "org/teamspace",
        "creator": "justus",
        "status": "Running",
        "studio": "my-studio",
        "machine": "A100",
        "image": "ubuntu",
        "cloud-account": "my-account",
        "started": "2026-08-03 09:30",
        "stopped": "2026-08-03 10:30",
    }

    assert set(patterns) == set(LIST_KEYS), "a new key needs a value here to prove it filters"

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace):
        for key, pattern in patterns.items():
            kept = CliRunner().invoke(list_jobs, ["--filter", f"{key}={pattern}", "--json"])
            dropped = CliRunner().invoke(list_jobs, ["--filter", f"{key}=no-job-looks-like-this", "--json"])

            assert [row["name"] for row in json.loads(kept.output)] == ["full"], key
            assert json.loads(dropped.output) == [], key


@mock_command_logging
def test_job_list_filters_by_glob_pattern() -> None:
    teamspace = _teamspace_with_jobs()

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace):
        result = CliRunner().invoke(list_jobs, ["--filter", "name=dist*", "--json"])

    assert result.exit_code == 0, result.output
    assert [row["name"] for row in json.loads(result.output)] == ["distributed"]


@mock_command_logging
def test_job_list_filter_keeps_a_comma_inside_a_glob_pattern() -> None:
    teamspace = _teamspace_with_jobs()
    teamspace.list_jobs.return_value[0].name = "job-0"

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace):
        result = CliRunner().invoke(list_jobs, ["--filter", "name=job-[0,1]", "--json"])

    assert result.exit_code == 0, result.output
    assert [row["name"] for row in json.loads(result.stdout)] == ["job-0"]


@mock_command_logging
def test_job_list_filter_matches_whole_value_and_ignores_case() -> None:
    teamspace = _teamspace_with_jobs()

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace):
        exact = CliRunner().invoke(list_jobs, ["--filter", "status=RUNNING", "--json"])
        partial = CliRunner().invoke(list_jobs, ["--filter", "status=run", "--json"])

    assert exact.exit_code == 0, exact.output
    assert len(json.loads(exact.output)) == 2
    assert json.loads(partial.output) == []


@mock_command_logging
def test_job_list_comma_separated_and_repeated_filters_must_all_match() -> None:
    teamspace = _teamspace_with_jobs()

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace):
        comma_separated = CliRunner().invoke(list_jobs, ["--filter", "creator=justus, name=single", "--json"])
        repeated = CliRunner().invoke(list_jobs, ["--filter", "creator=justus", "--filter", "name=single", "--json"])
        conflicting = CliRunner().invoke(list_jobs, ["--filter", "creator=justus,name=dist*", "--json"])

    assert [row["name"] for row in json.loads(comma_separated.output)] == ["single"]
    assert [row["name"] for row in json.loads(repeated.output)] == ["single"]
    assert json.loads(conflicting.output) == []


def test_job_list_filter_flattens_comma_separated_values() -> None:
    assert _resolve_filters(["name=train-*,status=running"]) == (("name", "train-*"), ("status", "running"))
    assert _resolve_filters(["name=a", "status=b"]) == (("name", "a"), ("status", "b"))
    assert _resolve_filters(["  creator = justus "]) == (("creator", "justus"),)
    # Only a comma introducing the next KEY= pair separates filters; the rest belong to the pattern.
    assert _resolve_filters(["name=job-[0,1]"]) == (("name", "job-[0,1]"),)
    assert _resolve_filters(["image=repo/img:a,b,status=running"]) == (
        ("image", "repo/img:a,b"),
        ("status", "running"),
    )
    # An empty pattern is a real filter: it keeps only the jobs with no value for that key.
    assert _resolve_filters(["studio="]) == (("studio", ""),)
    assert _resolve_filters([""]) == ()


@mock_command_logging
def test_job_list_filters_by_timestamp_prefix() -> None:
    teamspace = _teamspace_with_jobs()

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace):
        result = CliRunner().invoke(list_jobs, ["--filter", "started=2026-08-02*", "--json"])

    assert result.exit_code == 0, result.output
    assert [row["name"] for row in json.loads(result.output)] == ["distributed"]


@mock_command_logging
def test_job_list_filter_rejects_unknown_key_and_missing_pattern() -> None:
    teamspace = _teamspace_with_jobs()

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace):
        unknown = CliRunner().invoke(list_jobs, ["--filter", "owner=justus", "--json"])
        malformed = CliRunner().invoke(list_jobs, ["--filter", "creator", "--json"])

    assert unknown.exit_code != 0
    assert "unknown key 'owner'" in unknown.output
    assert "creator" in unknown.output
    assert malformed.exit_code != 0
    assert "expected KEY=PATTERN" in malformed.output


@mock_command_logging
def test_job_list_table_shows_creator() -> None:
    teamspace = _teamspace_with_jobs()
    console = Console(file=io.StringIO(), width=400)

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.list.Console", return_value=console
    ):
        result = CliRunner().invoke(list_jobs, [])

    assert result.exit_code == 0, result.output
    lines = console.file.getvalue().splitlines()
    assert "Creator" in next(line for line in lines if "Name" in line)
    assert "justus" in next(line for line in lines if "single" in line)
