import sys
from unittest.mock import patch

import pytest

from lightning_sdk.cli.edit import route_edit_operation
from lightning_sdk.cli.edit.edit import _drive_url, _quiet_transfer, _resolve_editor
from tests.cli.help import assert_help_contains, mock_command_logging

REMOTE = "lit://my-org/my-teamspace/uploads/notes.txt"


@mock_command_logging
def test_edit_help() -> None:
    assert_help_contains(
        "lightning edit --help",
        "Usage: lightning edit [OPTIONS] PATH",
        "Edit a file in place.",
    )


def test_resolve_editor_precedence(monkeypatch):
    monkeypatch.setenv("EDITOR", "nano")
    assert _resolve_editor("code -w") == "code -w"  # first --editor
    assert _resolve_editor(None) == "nano"  # then $EDITOR
    monkeypatch.delenv("EDITOR")
    assert _resolve_editor(None) == "vi"  # then default


def test_drive_url_encodes_nested_studio_path(monkeypatch):
    monkeypatch.delenv("LIGHTNING_CLOUD_URL", raising=False)
    url = _drive_url(
        "lit://lightning-ai/coding-model-training/studios/liana-dataset-dev-cluster"
        "/coding-model-training/dataset/repos.txt"
    )
    assert url == (
        "https://lightning.ai/lightning-ai/coding-model-training/drive"
        "?path=studios%2Fliana-dataset-dev-cluster%2Fcoding-model-training%2Fdataset%2Frepos.txt"
    )


def test_quiet_transfer_suppresses_output_on_success(capsys):
    with _quiet_transfer():
        print("chatty stdout line")
        print("chatty stderr line", file=sys.stderr)
    captured = capsys.readouterr()
    assert "chatty stdout line" not in captured.out
    assert "chatty stderr line" not in captured.err


def test_quiet_transfer_reemits_output_on_failure(capsys):
    def _failing_transfer():
        with _quiet_transfer():
            print("diagnostic that must survive")
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        _failing_transfer()
    captured = capsys.readouterr()
    # captured output is re-emitted to stderr so failures stay debuggable
    assert "diagnostic that must survive" in captured.err


def test_edit_requires_remote_url():
    with pytest.raises(ValueError, match="must be a remote lit:// URL"):
        route_edit_operation("/local/file.txt")


def test_edit_requires_a_file_path():
    with pytest.raises(ValueError, match="must point to a file"):
        route_edit_operation("lit://my-org/my-teamspace/uploads/")


def _fake_download(contents_by_call):
    """Return a route_cp_operation stub that writes the given contents on each download call."""
    calls = []

    def _stub(source, destination, recursive=False, progress_bar=True):
        calls.append((source, destination))
        if source.startswith("lit://"):
            # download: materialize the given contents locally
            with open(destination, "w") as f:
                f.write(contents_by_call.pop(0))

    return _stub, calls


@patch("lightning_sdk.cli.edit.edit.subprocess.call", return_value=0)
@patch("lightning_sdk.cli.edit.edit.route_cp_operation")
def test_edit_uploads_when_changed(mock_cp, mock_editor):
    stub, calls = _fake_download(["original"])
    mock_cp.side_effect = stub

    # the "editor" rewrites the file's contents
    def _edit(cmd):
        path = cmd[-1]
        with open(path, "w") as f:
            f.write("edited")
        return 0

    mock_editor.side_effect = _edit

    route_edit_operation(REMOTE)

    # one download (lit -> local) then one upload (local -> lit)
    assert len(calls) == 2
    assert calls[0][0] == REMOTE  # download source
    assert calls[1][1] == REMOTE  # upload destination


@patch("lightning_sdk.cli.edit.edit.subprocess.call", return_value=0)
@patch("lightning_sdk.cli.edit.edit.route_cp_operation")
def test_edit_skips_upload_when_unchanged(mock_cp, mock_editor):
    stub, calls = _fake_download(["same"])
    mock_cp.side_effect = stub
    mock_editor.side_effect = lambda cmd: 0  # editor changes nothing

    route_edit_operation(REMOTE)

    # only the download happened, no upload
    assert len(calls) == 1
    assert calls[0][0] == REMOTE


@patch("lightning_sdk.cli.edit.edit.subprocess.call", return_value=1)
@patch("lightning_sdk.cli.edit.edit.route_cp_operation")
def test_edit_skips_upload_when_editor_fails(mock_cp, mock_editor):
    stub, calls = _fake_download(["original"])
    mock_cp.side_effect = stub

    def _edit(cmd):
        with open(cmd[-1], "w") as f:
            f.write("edited")
        return 1  # non-zero exit

    mock_editor.side_effect = _edit

    route_edit_operation(REMOTE)

    assert len(calls) == 1  # download only; failed editor exit blocks upload


@patch("lightning_sdk.cli.edit.edit.subprocess.call", side_effect=FileNotFoundError())
@patch("lightning_sdk.cli.edit.edit.route_cp_operation")
def test_edit_missing_editor_raises(mock_cp, mock_editor):
    stub, _ = _fake_download(["original"])
    mock_cp.side_effect = stub

    with pytest.raises(ValueError, match="Could not launch editor"):
        route_edit_operation(REMOTE, editor="definitely-not-an-editor")
