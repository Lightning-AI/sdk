import subprocess

import pytest

from lightning_sdk.cli.legacy.exceptions import StudioCliError
from lightning_sdk.cli.legacy.upload import _file, _folder


def test_upload_help():
    result = subprocess.run("lightning upload --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning upload [OPTIONS] COMMAND [ARGS]...

  Upload assets to Lightning AI.

Options:
  --help  Show this message and exit.

Commands:
  container  Upload a container to Lightning AI's container registry.
  file       [DEPRECATED] Use 'lightning studio cp' instead.
  folder     [DEPRECATED] Use 'lightning studio cp -r' instead.
  model      Upload a model a teamspace.
"""
    )


def test_container_help():
    result = subprocess.run("lightning upload container --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning upload container [OPTIONS] CONTAINER

  Upload a container to Lightning AI's container registry.

Options:
  --tag TEXT                      The tag of the container to upload.
  --teamspace TEXT                The teamspace the studio is part of. Should
                                  be of format <OWNER>/<TEAMSPACE_NAME>. If
                                  not specified, tries to infer from the
                                  environment (e.g. when run from within a
                                  Studio.)
  --cloud-account, --cloud_account TEXT
                                  The name of the cloud account to store the
                                  Container in.
  --platform TEXT                 This is the platform the container pulled
                                  and push to Lightning AI will run on.
  --help                          Show this message and exit.
"""
    )


def test_file_help():
    result = subprocess.run("lightning upload file --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert result.returncode != 0
    assert "Use 'lightning studio cp' instead" in result_text
    assert "DeprecatedError" in result_text


def test_folder_help():
    result = subprocess.run("lightning upload folder --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert result.returncode != 0
    assert "Use 'lightning studio cp -r' instead" in result_text
    assert "DeprecatedError" in result_text


def test_model_help():
    result = subprocess.run("lightning upload model --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning upload model [OPTIONS] NAME

  Upload a model a teamspace.

  Example:     lightning upload model NAME

  NAME: the name of the model to upload (Should be of format <ORGANIZATION-
  NAME>/<TEAMSPACE-NAME>/<MODEL-NAME>).

Options:
  --path TEXT                     The path to the file or directory you want
                                  to upload. Defaults to the current
                                  directory.
  --cloud-account, --cloud_account TEXT
                                  The name of the cloud account to store the
                                  Model in.
  --help                          Show this message and exit.
"""
    )


def test_upload_folder_validation_is_a_file(tmp_path):
    path = tmp_path / "hello.txt"
    path.write_text("test", encoding="utf-8")

    with pytest.raises(StudioCliError):
        _folder(path)


def test_upload_folder_validation_not_exists(tmp_path):
    path = tmp_path / "files"

    with pytest.raises(FileNotFoundError):
        _folder(path)


def test_upload_file_validation_not_exists(tmp_path):
    path = tmp_path / "file.txt"

    with pytest.raises(FileNotFoundError):
        _file(path)


def test_upload_file_validation_is_a_folder(tmp_path):
    path = tmp_path / "files"
    path.mkdir()

    with pytest.raises(StudioCliError):
        _file(path)
