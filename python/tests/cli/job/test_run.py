from typing import Dict
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from lightning_sdk.cli.job.run import run_job
from lightning_sdk.cli.legacy.run import _resolve_envs, _resolve_path_mapping
from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_job_run_help() -> None:
    assert_help_contains(
        "lightning job run --help",
        "Usage: lightning job run",
        "Run async workloads using a docker image or studio.",
    )


@mock_command_logging
def test_jobs_run_help() -> None:
    assert_help_contains(
        "lightning jobs run --help",
        "Usage: lightning jobs run",
        "Run async workloads using a docker image or studio.",
    )


@mock_command_logging
def test_run_help() -> None:
    text = assert_help_contains(
        "lightning run --help",
        "`lightning run` has moved to noun-first commands:",
        "job -> lightning job run",
        "mmt -> lightning mmt run",
    )
    assert "Deprecation warning:" not in text


@mock_command_logging
def test_run_job_legacy_help() -> None:
    assert_help_contains(
        "lightning run job --help",
        "Deprecation warning:",
        "Use `lightning job run` instead of `lightning run job`.",
        "Usage: lightning run job [OPTIONS]",
    )


@mock_command_logging
def test_run_job_with_cloud(monkeypatch):
    from unittest.mock import MagicMock

    from click.testing import CliRunner

    from lightning_sdk.cli.job.run import run_job

    mock_job = MagicMock()
    monkeypatch.setattr("lightning_sdk.cli.job.run.Job", mock_job)
    monkeypatch.setattr("lightning_sdk.cli.job.run.resolve_teamspace", MagicMock(return_value="teamspace"))

    result = CliRunner().invoke(
        run_job,
        ["--name", "test-job", "--image", "ubuntu", "--command", "echo hi", "--cloud", "aws"],
    )

    assert result.exit_code == 0, result.output
    assert mock_job.run.call_args.kwargs["cloud"] == "aws"


@mock_command_logging
def test_run_job_with_multiple_machines_uses_mmt() -> None:
    submitted = MagicMock(name="distributed")
    submitted.name = "distributed"
    with patch("lightning_sdk.cli.job.run.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.job.run.Job.run"
    ) as run_single, patch(
        "lightning_sdk.cli.job.run.MMT.run",
        return_value=submitted,
    ) as run_mmt:
        result = CliRunner().invoke(
            run_job,
            ["--name", "distributed", "--image", "ubuntu", "--num-machines", "3"],
        )

    assert result.exit_code == 0, result.output
    run_single.assert_not_called()
    assert run_mmt.call_args.kwargs["num_machines"] == 3
    assert "Submitted job distributed." in result.output


@pytest.mark.parametrize(
    ("input_mappings", "expected"),
    [
        ("", {}),
        ("container_path1:connection_1:path1", {"container_path1": "connection_1:path1"}),
        (
            "container_path1:connection_1,/container_path_2:connection-2:path2, /container-path3:connection-3",
            {
                "container_path1": "connection_1",
                "/container_path_2": "connection-2:path2",
                "/container-path3": "connection-3",
            },
        ),
    ],
)
@mock_command_logging
def test_parse_run_path_mapping(input_mappings: str, expected: Dict[str, str]) -> None:
    assert _resolve_path_mapping(input_mappings) == expected


@pytest.mark.parametrize(
    ("input_env", "expected"),
    [
        ("", {}),
        ("ENV=abc", {"ENV": "abc"}),
        ('{"ENV":"abc"}', {"ENV": "abc"}),
        ('{"key1":"value1","key2":"value2"}', {"key1": "value1", "key2": "value2"}),
    ],
)
@mock_command_logging
def test_resolve_envs(input_env: str, expected: Dict[str, str]) -> None:
    assert _resolve_envs(input_env) == expected


@pytest.mark.parametrize("input_env", ["some-invalid-input", '["invalid"]', '{"not closed":'])
@mock_command_logging
def test_resolve_invalid_envs(input_env: str) -> None:
    with pytest.raises(ValueError, match="cannot be parsed as environment variable"):
        _resolve_envs(input_env)


@pytest.mark.parametrize(
    ("extra_args", "expected_entrypoint"),
    [
        (["--studio", "my-studio", "--command", "echo hello"], None),
        (["--image", "alpine:latest", "--command", "echo hello"], None),
        (["--image", "alpine:latest", "--command", "echo hello", "--entrypoint", "/bin/bash"], "/bin/bash"),
    ],
)
@mock_command_logging
def test_job_run_entrypoint_default(extra_args: list[str], expected_entrypoint: str | None) -> None:
    runner = CliRunner()
    args = ["--name", "test-job", "--teamspace", "my-ts", *extra_args]

    with patch("lightning_sdk.cli.job.run.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.job.run.Job.run", return_value=MagicMock()
    ) as mock_run:
        result = runner.invoke(run_job, args)

    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs["entrypoint"] == expected_entrypoint


@mock_command_logging
def test_run_job_json(monkeypatch) -> None:
    import json
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from click.testing import CliRunner

    from lightning_sdk.cli.job.run import run_job

    job = SimpleNamespace(id="job-abc", name="test-job", link="https://lightning.ai/acme/ts/jobs/job-abc")
    mock_job = MagicMock()
    mock_job.run.return_value = job
    monkeypatch.setattr("lightning_sdk.cli.job.run.Job", mock_job)
    ts = SimpleNamespace(name="ts", owner=SimpleNamespace(name="acme"))
    monkeypatch.setattr("lightning_sdk.cli.job.run.resolve_teamspace", MagicMock(return_value=ts))

    result = CliRunner().invoke(run_job, ["--name", "test-job", "--image", "ubuntu", "--command", "echo hi", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "id": "job-abc",
        "name": "test-job",
        "teamspace": "acme/ts",
        "link": "https://lightning.ai/acme/ts/jobs/job-abc",
    }
