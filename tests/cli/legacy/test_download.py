import os
import subprocess

from lightning_sdk.cli.legacy.download import _expand_remote_path


def test_download_help():
    result = subprocess.run("lightning download --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning download [OPTIONS] COMMAND [ARGS]...

  Download resources from Lightning AI.

Options:
  --help  Show this message and exit.

Commands:
  container  Download a docker container from a teamspace.
  file       [DEPRECATED] Use 'lightning studio cp' instead.
  folder     [DEPRECATED] Use 'lightning studio cp -r' instead.
  license    Download license for specific products/packages.
  licenses   Download licenses for all user's products/packages.
  model      Download a model from a teamspace.
"""
    )


def test_container_help():
    result = subprocess.run("lightning download container --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning download container [OPTIONS] CONTAINER

  Download a docker container from a teamspace.

  Example:   lightning download container CONTAINER

  CONTAINER: The name of the container to download.

Options:
  --teamspace TEXT                The name of the teamspace to download the
                                  container from
  --tag TEXT                      The tag of the container to download.
                                  [default: latest]
  --cloud-account, --cloud_account TEXT
                                  The name of the cloud account to download
                                  the Container from.
  --help                          Show this message and exit.
"""
    )


def test_file_help():
    result = subprocess.run("lightning download file --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert result.returncode != 0
    assert "Use 'lightning studio cp' instead" in result_text
    assert "DeprecatedError" in result_text


def test_folder_help():
    result = subprocess.run("lightning download folder --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert result.returncode != 0
    assert "Use 'lightning studio cp -r' instead" in result_text
    assert "DeprecatedError" in result_text


def test_model_help():
    result = subprocess.run("lightning download model --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning download model [OPTIONS] NAME

  Download a model from a teamspace.

  Example:   lightning download model NAME

  NAME: The name of the model to download in the format of <ORGANIZATION-
  NAME>/<TEAMSPACE-NAME>/<MODEL-NAME>.

Options:
  --download-dir, --download_dir TEXT
                                  The directory where the Model should be
                                  downloaded.
  --help                          Show this message and exit.
"""
    )


def test_licenses_help():
    result = subprocess.run("lightning download licenses --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning download licenses [OPTIONS]

  Download licenses for all user's products/packages.

  Example:   lightning download licenses

Options:
  --help  Show this message and exit.
"""
    )


def test_license_help():
    result = subprocess.run("lightning download license --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning download license [OPTIONS] NAME

  Download license for specific products/packages.

  Example:   lightning download license NAME

  NAME: The name of the product/package to download the license for.

Options:
  --help  Show this message and exit.
"""
    )


def test_expand_path():
    assert _expand_remote_path("~/test") == "test"
    assert _expand_remote_path("~/test/test2") == "test/test2"
    assert _expand_remote_path("~/") == ""
    assert _expand_remote_path("~") == ""
    assert _expand_remote_path("") == ""
    assert _expand_remote_path("/") == ""
    assert _expand_remote_path(os.path.expanduser("~")) == ""
