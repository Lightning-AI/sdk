import subprocess


def test_connect_help():
    result = subprocess.run("lightning connect --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning connect [OPTIONS] COMMAND [ARGS]...

  Connect to lightning products.

Options:
  --help  Show this message and exit.

Commands:
  studio  Connect to a studio via SSH.
"""
    )


def test_studio_help():
    result = subprocess.run("lightning connect studio --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning connect studio [OPTIONS]

  Connect to a studio via SSH.

Options:
  --name TEXT       The name of the studio to connect to.
  --teamspace TEXT  The teamspace the studio is part of. Should be of format
                    <OWNER>/<TEAMSPACE_NAME>.
  --help            Show this message and exit.
"""
    )
