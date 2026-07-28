from io import StringIO
from unittest.mock import MagicMock, patch

from rich.console import Console

from lightning_sdk.cli.legacy.upload import _print_docker_push
from tests.cli.help import assert_help_contains, mock_command_logging


def test_container_upload_result_prints_url_without_opening_browser() -> None:
    """A completed legacy container upload must report its URL without launching a browser."""
    output = StringIO()
    console = Console(file=output)

    with patch("webbrowser.open", side_effect=AssertionError("browser must not open")):
        _print_docker_push(iter([{"finish": True, "url": "https://lightning.test/container"}]), console, MagicMock(), 1)

    assert "https://lightning.test/container" in output.getvalue()


@mock_command_logging
def test_container_upload_help() -> None:
    assert_help_contains(
        "lightning container upload --help",
        "Usage: lightning container upload",
        "Upload a container to Lightning AI's container registry.",
    )


@mock_command_logging
def test_containers_upload_help() -> None:
    assert_help_contains(
        "lightning containers upload --help",
        "Usage: lightning containers upload",
        "Upload a container to Lightning AI's container registry.",
    )


@mock_command_logging
def test_upload_help() -> None:
    text = assert_help_contains(
        "lightning upload --help",
        "`lightning upload` has moved to noun-first commands:",
        "container -> lightning container upload",
        "file -> lightning cp",
        "folder -> lightning cp -r",
        "model -> lightning model upload",
    )
    assert "Deprecation warning:" not in text


@mock_command_logging
def test_upload_container_legacy_help() -> None:
    assert_help_contains(
        "lightning upload container --help",
        "Deprecation warning:",
        "Use `lightning container upload` instead of `lightning upload container`.",
        "Usage: lightning upload container [OPTIONS] CONTAINER",
    )
