import subprocess


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
  file       Download a file from a Studio.
  folder     Download a folder from a Studio.
  licenses   Download licenses for all products/packages.
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

  Download a file from a Studio.

  Example:   lightning download file PATH

  PATH: The relative path to the file within the Studio you want to download.

Options:
  --studio TEXT                   The name of the studio to upload to. Will
                                  show a menu with user's owned studios for
                                  selection if not specified. If provided,
                                  should be in the form of <TEAMSPACE-
                                  NAME>/<STUDIO-NAME> where the names are
                                  case-sensitive. The teamspace and studio
                                  names can be regular expressions to match, a
                                  menu filtered studios will be shown for
                                  final selection.
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

  Download a folder from a Studio.

  Example:   lightning download folder PATH

  PATH: The relative path within the Studio you want to download. Defaults to
  the entire studio.

Options:
  --studio TEXT                   The name of the studio to upload to. Will
                                  show a menu with user's owned studios for
                                  selection if not specified. If provided,
                                  should be in the form of <TEAMSPACE-
                                  NAME>/<STUDIO-NAME> where the names are
                                  case-sensitive. The teamspace and studio
                                  names can be regular expressions to match, a
                                  menu filtered studios will be shown for
                                  final selection.
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

  Download licenses for all products/packages.

  Example:   lightning download licenses

Options:
  --help  Show this message and exit.
"""
    )
