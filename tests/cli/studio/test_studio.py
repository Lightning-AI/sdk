import subprocess


def test_studio_help():
    result = subprocess.run("lightning studio --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning studio [OPTIONS] COMMAND [ARGS]...

  Manage Lightning AI Studios.

Options:
  --help  Show this message and exit.

Commands:
  connect  Connect to a Studio.
  cp       Copy a Studio file.
  create   Create a new Studio.
  delete   Delete a Studio.
  list     List Studios in a teamspace.
  ls       List contents of a directory in Studio.
  rm       Remove a Studio file or directory.
  ssh      SSH into a Studio.
  start    Start a Studio.
  stop     Stop a Studio.
  switch   Switch a Studio to a different machine type.
"""
    )
