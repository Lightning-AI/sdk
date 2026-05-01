import os

from lightning_sdk.cli.legacy.download import _expand_remote_path
from tests.cli.help import assert_help_contains


def test_file_download_help() -> None:
    assert_help_contains(
        "lightning file download --help",
        "Usage: lightning file download",
        "Download a file from a Studio or Teamspace drive file.",
    )


def test_files_download_help() -> None:
    assert_help_contains(
        "lightning files download --help",
        "Usage: lightning files download",
        "Download a file from a Studio or Teamspace drive file.",
    )


def test_download_file_legacy_help() -> None:
    assert_help_contains(
        "lightning download file --help",
        "Deprecation warning:",
        "Use `lightning file download` instead of `lightning download file`.",
        "Usage: lightning download file [OPTIONS] PATH",
    )


def test_expand_path() -> None:
    assert _expand_remote_path("~/test") == "test"
    assert _expand_remote_path("~/test/test2") == "test/test2"
    assert _expand_remote_path("~/") == ""
    assert _expand_remote_path("~") == ""
    assert _expand_remote_path("") == ""
    assert _expand_remote_path("/") == ""
    assert _expand_remote_path(os.path.expanduser("~")) == ""
