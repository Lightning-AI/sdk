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
        total_cost=1.0,
        _guaranteed_job=SimpleNamespace(spec=SimpleNamespace(instance_name="cpu-1", instance_type=None, cluster_id="")),
        _prevent_refetch_latest=False,
    )
    multi = SimpleNamespace(
        name="distributed",
        teamspace=teamspace,
        studio_name=None,
        image="ubuntu",
        status="Running",
        num_machines=4,
        total_cost=4.0,
        _guaranteed_job=SimpleNamespace(spec=SimpleNamespace(instance_name="cpu-1", instance_type=None, cluster_id="")),
        _prevent_refetch_latest=False,
    )
    teamspace.jobs = [single, multi]
    teamspace.multi_machine_jobs = [multi]
    return teamspace


@mock_command_logging
def test_job_list_includes_single_and_multi_machine_jobs() -> None:
    teamspace = _teamspace_with_jobs()

    with (
        patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace),
        patch("lightning_sdk.cli.job.list._machine_label", return_value="CPU"),
    ):
        result = CliRunner().invoke(list_jobs, ["--json"])

    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert [(row["name"], row["num_machines"]) for row in rows] == [
        ("distributed", 4),
        ("single", 1),
    ]


@mock_command_logging
def test_job_list_sort_by_cloud_account_without_attribute() -> None:
    teamspace = _teamspace_with_jobs()

    with (
        patch("lightning_sdk.cli.job.list.resolve_teamspace", return_value=teamspace),
        patch("lightning_sdk.cli.job.list._machine_label", return_value="CPU"),
    ):
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
