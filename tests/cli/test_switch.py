import subprocess


def test_switch_help():
    result = subprocess.run("lightning switch --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning switch [OPTIONS] COMMAND [ARGS]...

  Switch machines for resources on the Lightning AI platform.

Options:
  --help  Show this message and exit.

Commands:
  studio  Switch a studio to a given machine.
"""
    )


def test_studio_help():
    result = subprocess.run("lightning switch studio --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning switch studio [OPTIONS] NAME

  Switch a studio to a given machine.

  Example:   lightning switch studio NAME --machine=CPU

  NAME: the name of the studio to switch machine for.

Options:
  --teamspace TEXT                The teamspace the studio is part of. Should
                                  be of format <OWNER>/<TEAMSPACE_NAME>. If
                                  not specified, tries to infer from the
                                  environment (e.g. when run from within a
                                  Studio.)
  --machine [CPU|DATA_PREP|DATA_PREP_MAX|DATA_PREP_ULTRA|T4|T4_X_4|L4|L4_X_4|L4_X_8|A10G|A10G_X_4|A10G_X_8|L40S|L40S_X_4|L40S_X_8|A100_X_8|H100_X_8|H200_X_8]
                                  The machine type to switch to.  [default:
                                  CPU]
  --help                          Show this message and exit.
"""  # noqa: E501
    )
