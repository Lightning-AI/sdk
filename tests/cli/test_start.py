import subprocess


def test_start_help():
    result = subprocess.run("lightning start --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning start [OPTIONS] COMMAND [ARGS]...

  Start resources on the Lightning AI platform.

Options:
  --help  Show this message and exit.

Commands:
  studio
"""
    )


def test_studio_help():
    result = subprocess.run("lightning start studio --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning start studio [OPTIONS]

Options:
  --name TEXT                     The name of the studio to start. If not
                                  specified, tries to infer from the
                                  environment (e.g. when run from within a
                                  Studio.)
  --teamspace TEXT                The teamspace the studio is part of. Should
                                  be of format <OWNER>/<TEAMSPACE_NAME>. If
                                  not specified, tries to infer from the
                                  environment (e.g. when run from within a
                                  Studio.)
  --machine [CPU_SMALL|CPU|DATA_PREP|DATA_PREP_MAX|DATA_PREP_ULTRA|T4|T4_X_4|L4|L4_X_4|L4_X_8|A10G|A10G_X_4|A10G_X_8|L40S|L40S_X_4|L40S_X_8|A100_X_8|H100_X_8|H200_X_8]
                                  The machine type to start the studio on.
                                  [default: CPU]
  --help                          Show this message and exit.
"""  # noqa: E501
    )
