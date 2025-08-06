import os
import subprocess

from lightning_sdk.cli.download import _expand_remote_path


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
  file       Download a file from a Studio or Teamspace drive file.
  folder     Download a folder from a Studio or a Teamspace drive folder.
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

    assert (
        result_text
        == """Usage: lightning download file [OPTIONS] PATH

  Download a file from a Studio or Teamspace drive file.

  Example:   lightning download file PATH

  PATH: The relative path to the file within the Studio or Teamspace drive
  file you want to download.

Options:
  --studio TEXT                   The name of the studio to download from.
                                  Will show a menu with user's owned studios
                                  for selection if not specified. If provided,
                                  should be in the form of <TEAMSPACE-
                                  NAME>/<STUDIO-NAME> where the names are
                                  case-sensitive. The teamspace and studio
                                  names can be regular expressions to match, a
                                  menu filtered studios will be shown for
                                  final selection.
  --teamspace TEXT                The teamspace the file is part of. Should be
                                  of format <OWNER>/<TEAMSPACE_NAME>.
  --local-path, --local_path DIRECTORY
                                  The path to the directory you want to
                                  download the file to.
  --help                          Show this message and exit.
"""
    )


def test_folder_help():
    result = subprocess.run("lightning download folder --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning download folder [OPTIONS] PATH

  Download a folder from a Studio or a Teamspace drive folder.

  Example:   lightning download folder PATH

  PATH: The relative path within the Studio or drive folder you want to
  download. Defaults to the entire Studio or drive folder.

Options:
  --studio TEXT                   The name of the studio to download from.
                                  Will show a menu with user's owned studios
                                  for selection if not specified. If provided,
                                  should be in the form of <TEAMSPACE-
                                  NAME>/<STUDIO-NAME> where the names are
                                  case-sensitive. The teamspace and studio
                                  names can be regular expressions to match, a
                                  menu filtered studios will be shown for
                                  final selection.
  --teamspace TEXT                The teamspace the drive folder is part of.
                                  Should be of format
                                  <OWNER>/<TEAMSPACE_NAME>.
  --local-path, --local_path DIRECTORY
                                  The path to the directory you want to
                                  download the folder to.
  --help                          Show this message and exit.
"""
    )


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
