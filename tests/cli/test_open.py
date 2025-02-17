import os
from pathlib import Path
from unittest import mock

from click.testing import CliRunner

from lightning_sdk.cli.open import open


@mock.patch.dict(os.environ, {"LIGHTNING_CLOUD_URL": "lightning.ai:443"}, clear=True)
@mock.patch("lightning_sdk.cli.open.webbrowser")
@mock.patch("lightning_sdk.cli.open.Studio")
@mock.patch("lightning_sdk.cli.open.Teamspace")
@mock.patch("lightning_sdk.cli.open._upload_folder")
def test_open_folder(mock_upload_folder, mock_teamspace, mock_studio, mock_webbrowser, tmpdir):
    mock_studio().owner.name = "owner-name"
    mock_studio().teamspace.name = "teamspace-name"
    mock_studio().name = "studio-name"

    runner = CliRunner()
    result = runner.invoke(open, [f"{tmpdir}"])
    assert result.exit_code == 0, result.output

    mock_upload_folder.assert_called_once()

    mock_webbrowser.open.assert_called_once_with(
        "lightning.ai/owner-name/teamspace-name/studios/studio-name/code?turnOn=true"
    )


@mock.patch.dict(os.environ, {"LIGHTNING_CLOUD_URL": "lightning.ai:443"}, clear=True)
@mock.patch("lightning_sdk.cli.open.webbrowser")
@mock.patch("lightning_sdk.cli.open.Studio")
@mock.patch("lightning_sdk.cli.open.Teamspace")
@mock.patch("lightning_sdk.cli.open._upload_folder")
def test_open_file(mock_upload_folder, mock_teamspace, mock_studio, mock_webbrowser, tmpdir):
    mock_studio().owner.name = "owner-name"
    mock_studio().teamspace.name = "teamspace-name"
    mock_studio().name = "studio-name"

    (Path(tmpdir) / "file.txt").touch()

    runner = CliRunner()
    result = runner.invoke(open, [f"{tmpdir}/file.txt"])
    assert result.exit_code == 0, result.output

    mock_upload_folder.assert_not_called()
    mock_studio().upload_file.assert_called_once()

    mock_webbrowser.open.assert_called_once_with(
        "lightning.ai/owner-name/teamspace-name/studios/studio-name/code?turnOn=true"
    )
