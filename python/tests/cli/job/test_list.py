import json
from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner

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


@mock_command_logging
def test_job_list_includes_single_and_multi_machine_jobs() -> None:
    owner = SimpleNamespace(name="org")
    teamspace = SimpleNamespace(name="teamspace", owner=owner)
    single = SimpleNamespace(
        name="single",
        teamspace=teamspace,
        studio=None,
        image="ubuntu",
        status="Running",
        machine="CPU",
        total_cost=1.0,
        cloud_account="default",
    )
    multi = SimpleNamespace(
        name="distributed",
        teamspace=teamspace,
        studio=None,
        image="ubuntu",
        status="Running",
        machine="CPU",
        num_machines=4,
        total_cost=4.0,
        cloud_account="default",
    )
    teamspace.jobs = [single]
    teamspace.multi_machine_jobs = [multi]

    with patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace):
        result = CliRunner().invoke(list_jobs, ["--json"])

    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert [(row["name"], row["num_machines"]) for row in rows] == [
        ("distributed", 4),
        ("single", 1),
    ]


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
