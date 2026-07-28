from pathlib import Path
from unittest import mock

from click.testing import CliRunner

from lightning_sdk.cli.legacy.open import open
from lightning_sdk.cli.studio.open import open_studio
from tests.cli.help import assert_help_contains, command_text, mock_command_logging


@mock_command_logging
def test_open_studio():
    result_text = command_text("lightning studio open --help")

    assert "Usage: lightning studio open [OPTIONS] [PATH]" in result_text
    assert "Open a local file or folder in a Lightning Studio." in result_text
    assert "--teamspace" in result_text
    assert "--cloud" in result_text
    assert "--cloud-account" not in result_text


@mock_command_logging
def test_studios_open_help() -> None:
    assert_help_contains(
        "lightning studios open --help",
        "Usage: lightning studios open",
        "Open a local file or folder in a Lightning Studio.",
    )


@mock_command_logging
def test_open_help_redirect() -> None:
    assert_help_contains(
        "lightning open --help",
        "Deprecation warning:",
        "Use `lightning studio open` instead of `lightning open`.",
        "Usage: lightning open [OPTIONS] [PATH]",
    )


@mock.patch.dict("os.environ", {"LIGHTNING_CLOUD_URL": "lightning.ai:443"}, clear=True)
@mock.patch("webbrowser.open", side_effect=AssertionError("browser must not open"))
@mock.patch("lightning_sdk.cli.legacy.open.Studio")
@mock.patch("lightning_sdk.cli.legacy.open.resolve_teamspace")
@mock.patch("lightning_sdk.cli.legacy.open._upload_folder")
@mock_command_logging
def test_open_folder(mock_upload_folder, resolve_teamspace, mock_studio, _webbrowser, tmpdir):
    mock_studio.return_value.owner.name = "owner-name"
    mock_studio.return_value.teamspace.name = "teamspace-name"
    mock_studio.return_value.name = "studio-name"

    (Path(tmpdir) / "folder").mkdir()
    (Path(tmpdir) / "folder" / "file.txt").touch()

    runner = CliRunner()
    result = runner.invoke(open, [f"{tmpdir}/folder", "--cloud", "test-cloud"])
    assert result.exit_code == 0, result.output

    mock_studio.assert_called_once_with(name="folder", teamspace=resolve_teamspace(), cloud="test-cloud")
    mock_upload_folder.assert_called_once()
    assert "lightning.ai/owner-name/teamspace-name/studios/studio-name/code?turnOn=true" in result.output


@mock.patch.dict("os.environ", {"LIGHTNING_CLOUD_URL": "lightning.ai:443"}, clear=True)
@mock.patch("webbrowser.open", side_effect=AssertionError("browser must not open"))
@mock.patch("lightning_sdk.cli.legacy.open.Studio")
@mock.patch("lightning_sdk.cli.legacy.open.resolve_teamspace")
@mock.patch("lightning_sdk.cli.legacy.open._upload_folder")
@mock_command_logging
def test_open_file(mock_upload_folder, resolve_teamspace, mock_studio, _webbrowser, tmpdir):
    mock_studio.return_value.owner.name = "owner-name"
    mock_studio.return_value.teamspace.name = "teamspace-name"
    mock_studio.return_value.name = "studio-name"

    (Path(tmpdir) / "file.txt").touch()

    runner = CliRunner()
    result = runner.invoke(open, [f"{tmpdir}/file.txt", "--cloud", "test-cloud"])
    assert result.exit_code == 0, result.output

    mock_studio.assert_called_once_with(name="file", teamspace=resolve_teamspace(), cloud="test-cloud")
    mock_upload_folder.assert_not_called()
    mock_studio().upload_file.assert_called_once()
    assert "lightning.ai/owner-name/teamspace-name/studios/studio-name/code?turnOn=true" in result.output


@mock.patch.dict("os.environ", {"LIGHTNING_CLOUD_URL": "lightning.ai:443"}, clear=True)
@mock.patch("webbrowser.open", side_effect=AssertionError("browser must not open"))
@mock.patch("lightning_sdk.cli.legacy.open.Studio")
@mock.patch("lightning_sdk.cli.legacy.open.resolve_teamspace")
@mock.patch("lightning_sdk.cli.legacy.open._upload_folder")
@mock_command_logging
def test_open_file_without_cloud_account(mock_upload_folder, resolve_teamspace, mock_studio, _webbrowser, tmpdir):
    mock_studio.return_value.owner.name = "owner-name"
    mock_studio.return_value.teamspace.name = "teamspace-name"
    mock_studio.return_value.name = "studio-name"
    mock_studio.return_value.cloud_account = "test-cloud"
    mock_studio.return_value.teamspace.owner.name = "owner-name"
    resolve_teamspace.return_value.name = "teamspace-name"
    resolve_teamspace.return_value.owner.name = "owner-name"
    (Path(tmpdir) / "file.txt").touch()

    runner = CliRunner()
    result = runner.invoke(open, [f"{tmpdir}/file.txt"])
    assert result.exit_code == 0, result.output

    mock_studio.assert_called_with(name="file", teamspace=resolve_teamspace(), cloud="test-cloud")
    mock_upload_folder.assert_not_called()
    mock_studio().upload_file.assert_called_once()
    assert "lightning.ai/owner-name/teamspace-name/studios/studio-name/code?turnOn=true" in result.output


@mock.patch("webbrowser.open", side_effect=AssertionError("browser must not open"))
@mock.patch("lightning_sdk.cli.studio.open.Studio")
@mock.patch("lightning_sdk.cli.studio.open.resolve_teamspace")
@mock.patch("lightning_sdk.cli.studio.open._upload_folder")
@mock_command_logging
def test_studio_open_passes_resume_policy(upload_folder, resolve_teamspace, studio_cls, _webbrowser, tmp_path) -> None:
    studio = studio_cls.return_value
    studio.owner.name = "owner-name"
    studio.teamspace.name = "teamspace-name"
    studio.name = "studio-name"

    result = CliRunner().invoke(open_studio, [str(tmp_path), "--resume"])

    assert result.exit_code == 0, result.output
    upload_folder.assert_called_once_with(
        str(tmp_path),
        remote_path=".",
        studio=studio,
        recovery="resume",
    )


@mock_command_logging
def test_studio_open_rejects_both_recovery_flags() -> None:
    result = CliRunner().invoke(open_studio, ["--resume", "--restart"])

    assert result.exit_code != 0
    assert "mutually exclusive" in result.output
