from typing import Dict

import pytest

from lightning_sdk.cli.legacy.run import _resolve_envs, _resolve_path_mapping
from tests.cli.help import assert_help_contains


def test_job_run_help() -> None:
    assert_help_contains(
        "lightning job run --help",
        "Usage: lightning job run",
        "Run async workloads using a docker image or studio.",
    )


def test_jobs_run_help() -> None:
    assert_help_contains(
        "lightning jobs run --help",
        "Usage: lightning jobs run",
        "Run async workloads using a docker image or studio.",
    )


def test_run_help() -> None:
    text = assert_help_contains(
        "lightning run --help",
        "`lightning run` has moved to noun-first commands:",
        "job -> lightning job run",
        "mmt -> lightning mmt run",
    )
    assert "Deprecation warning:" not in text


def test_run_job_legacy_help() -> None:
    assert_help_contains(
        "lightning run job --help",
        "Deprecation warning:",
        "Use `lightning job run` instead of `lightning run job`.",
        "Usage: lightning run job [OPTIONS]",
    )


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
def test_resolve_envs(input_env: str, expected: Dict[str, str]) -> None:
    assert _resolve_envs(input_env) == expected


@pytest.mark.parametrize("input_env", ["some-invalid-input", '["invalid"]', '{"not closed":'])
def test_resolve_invalid_envs(input_env: str) -> None:
    with pytest.raises(ValueError, match="cannot be parsed as environment variable"):
        _resolve_envs(input_env)
