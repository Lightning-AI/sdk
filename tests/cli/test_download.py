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
  --teamspace TEXT  The name of the teamspace to download the container from
  --tag TEXT        The tag of the container to download.  [default: latest]
  --help            Show this message and exit.
"""
    )


def test_file_help():
    result = subprocess.run("lightning download file --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning download file [OPTIONS]

  Download a file from a Studio.

Options:
  --path TEXT                     The relative path within the Studio you want
                                  to download. If you leave it empty it will
                                  download whole studio and locally creates a
                                  new folder with the same name as the
                                  selected studio.
  --studio TEXT                   The name of the studio to upload to. Will
                                  show a menu with user's owned studios for
                                  selection if not specified. If provided,
                                  should be in the form of <TEAMSPACE-
                                  NAME>/<STUDIO-NAME> where the names are
                                  case-sensitive. The teamspace and studio
                                  names can be regular expressions to match, a
                                  menu filtered studios will be shown for
                                  final selection.
  --local-path, --local_path TEXT
                                  The path to the directory you want to
                                  download the folder to.
  --help                          Show this message and exit.
"""
    )


def test_folder_help():
    result = subprocess.run("lightning download folder --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning download folder [OPTIONS]

  Download a folder from a Studio.

Options:
  --path TEXT                     The relative path within the Studio you want
                                  to download. If you leave it empty it will
                                  download whole studio and locally creates a
                                  new folder with the same name as the
                                  selected studio.
  --studio TEXT                   The name of the studio to upload to. Will
                                  show a menu with user's owned studios for
                                  selection if not specified. If provided,
                                  should be in the form of <TEAMSPACE-
                                  NAME>/<STUDIO-NAME> where the names are
                                  case-sensitive. The teamspace and studio
                                  names can be regular expressions to match, a
                                  menu filtered studios will be shown for
                                  final selection.
  --local-path, --local_path TEXT
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
