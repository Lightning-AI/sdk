import subprocess


def test_generate_help():
    result = subprocess.run("lightning generate --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning generate [OPTIONS] COMMAND [ARGS]...

  Generate configs (such as ssh for studio) and print them to commandline.

Options:
  --help  Show this message and exit.

Commands:
  ssh  Get SSH config entry for a studio.
"""
    )


def test_ssh_help():
    result = subprocess.run("lightning generate ssh --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning generate ssh [OPTIONS]

  Get SSH config entry for a studio.

Options:
  --name TEXT       The name of the studio to obtain SSH config. If not
                    specified, tries to infer from the environment (e.g. when
                    run from within a Studio.)
  --teamspace TEXT  The teamspace the studio is part of. Should be of format
                    <OWNER>/<TEAMSPACE_NAME>. If not specified, tries to infer
                    from the environment (e.g. when run from within a Studio.)
  --help            Show this message and exit.
"""
    )
