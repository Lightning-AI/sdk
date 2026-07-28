import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest

from lightning_sdk.cli.legacy.exceptions import StudioCliError
from lightning_sdk.cli.legacy.upload import (
    _folder,
    _resolve_previous_upload_state,
    resolve_upload_recovery,
)
from tests.cli.help import assert_help_contains, mock_command_logging


def create_upload_state(tmp_path: Path, state: dict[str, str]) -> Path:
    state_file = tmp_path / "upload.json"
    state_file.write_text(json.dumps(state))
    return state_file


def test_resolve_upload_recovery_rejects_both_flags() -> None:
    with pytest.raises(click.UsageError, match="mutually exclusive"):
        resolve_upload_recovery(resume=True, restart=True)


def test_incomplete_upload_requires_explicit_policy(tmp_path: Path) -> None:
    state_file = create_upload_state(tmp_path, {"a": "remote/a"})

    with patch(
        "lightning_sdk.cli.legacy.upload._upload_state_path",
        return_value=state_file,
    ), pytest.raises(click.UsageError, match="--resume.*--restart"):
        _resolve_previous_upload_state(
            studio=MagicMock(),
            remote_path=".",
            state_dict={"b": "remote/b"},
            recovery=None,
        )


def test_resume_without_state_fails(tmp_path: Path) -> None:
    with patch(
        "lightning_sdk.cli.legacy.upload._upload_state_path",
        return_value=tmp_path / "missing.json",
    ), pytest.raises(click.UsageError, match="nothing to resume"):
        _resolve_previous_upload_state(
            MagicMock(), ".", {"b": "remote/b"}, recovery="resume"
        )


def test_restart_ignores_existing_state(tmp_path: Path) -> None:
    current = {"current": "remote/current"}
    state_file = create_upload_state(tmp_path, {"old": "remote/old"})

    with patch(
        "lightning_sdk.cli.legacy.upload._upload_state_path",
        return_value=state_file,
    ):
        assert _resolve_previous_upload_state(
            MagicMock(), ".", current, recovery="restart"
        ) == current


@mock_command_logging
def test_folder_upload_help() -> None:
    assert_help_contains(
        "lightning folder upload --help", "Usage: lightning folder upload", "Upload a folder to a Studio."
    )


@mock_command_logging
def test_folders_upload_help() -> None:
    assert_help_contains(
        "lightning folders upload --help", "Usage: lightning folders upload", "Upload a folder to a Studio."
    )


@mock_command_logging
def test_upload_folder_legacy_help() -> None:
    assert_help_contains(
        "lightning upload folder --help",
        "Deprecation warning:",
        "Use `lightning cp -r` instead of `lightning upload folder`.",
        "Usage: lightning upload folder [OPTIONS] SOURCE [DESTINATION]",
    )


@mock_command_logging
def test_upload_folder_validation_is_a_file(tmp_path) -> None:
    path = tmp_path / "hello.txt"
    path.write_text("test", encoding="utf-8")

    with pytest.raises(StudioCliError):
        _folder(path)


@mock_command_logging
def test_upload_folder_validation_not_exists(tmp_path) -> None:
    path = tmp_path / "files"

    with pytest.raises(FileNotFoundError):
        _folder(path)
