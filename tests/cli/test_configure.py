import subprocess


def test_configure_help():
    result = subprocess.run("lightning configure --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning configure [OPTIONS] COMMAND [ARGS]...

  Configure access to resources on the Lightning AI platform.

Options:
  --help  Show this message and exit.

Commands:
  ssh  Get SSH config entry for a studio.
"""
    )


def test_ssh_help():
    result = subprocess.run("lightning configure ssh --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning configure ssh [OPTIONS]

  Get SSH config entry for a studio.

Options:
  --name TEXT       The name of the studio to obtain SSH config. If not
                    specified, tries to infer from the environment (e.g. when
                    run from within a Studio.)
  --teamspace TEXT  The teamspace the studio is part of. Should be of format
                    <OWNER>/<TEAMSPACE_NAME>. If not specified, tries to infer
                    from the environment (e.g. when run from within a Studio.)
  --overwrite       Whether to overwrite the SSH key and config if they
                    already exist.
  --help            Show this message and exit.
"""
    )
