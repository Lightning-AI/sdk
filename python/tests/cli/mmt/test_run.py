from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from lightning_sdk.cli.mmt.run import run_mmt
from tests.cli.help import assert_help_contains


def test_mmt_run_help() -> None:
    assert_help_contains(
        "lightning mmt run --help",
        "Usage: lightning mmt run",
        "Run async workloads on multiple machines using a docker image.",
    )


def test_mmts_run_help() -> None:
    assert_help_contains(
        "lightning mmts run --help",
        "Usage: lightning mmts run",
        "Run async workloads on multiple machines using a docker image.",
    )


def test_run_mmt_legacy_help() -> None:
    assert_help_contains(
        "lightning run mmt --help",
        "Deprecation warning:",
        "Use `lightning mmt run` instead of `lightning run mmt`.",
        "Usage: lightning run mmt [OPTIONS]",
    )


def test_run_mmt_with_cloud(monkeypatch):
    from unittest.mock import MagicMock

    from click.testing import CliRunner

    from lightning_sdk.cli.mmt.run import run_mmt

    mock_mmt = MagicMock()
    monkeypatch.setattr("lightning_sdk.cli.mmt.run.MMT", mock_mmt)
    monkeypatch.setattr("lightning_sdk.cli.mmt.run.Teamspace", MagicMock(return_value="teamspace"))

    result = CliRunner().invoke(
        run_mmt,
        ["--name", "test-mmt", "--image", "ubuntu", "--command", "echo hi", "--cloud", "aws"],
    )

    assert result.exit_code == 0, result.output
    assert mock_mmt.run.call_args.kwargs["cloud"] == "aws"


@pytest.mark.parametrize(
    ("extra_args", "expected_entrypoint"),
    [
        (["--studio", "my-studio", "--command", "echo hello"], None),
        (["--image", "alpine:latest", "--command", "echo hello"], None),
        (["--image", "alpine:latest", "--command", "echo hello", "--entrypoint", "/bin/bash"], "/bin/bash"),
    ],
)
def test_mmt_run_entrypoint_default(extra_args: list[str], expected_entrypoint: str | None) -> None:
    runner = CliRunner()
    args = ["--name", "test-mmt", "--teamspace", "my-ts", *extra_args]

    with patch("lightning_sdk.cli.mmt.run.Teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.mmt.run.MMT.run", return_value=MagicMock()
    ) as mock_run:
        result = runner.invoke(run_mmt, args)

    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs["entrypoint"] == expected_entrypoint
