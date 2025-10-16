import subprocess


def test_switch_studio():
    result = subprocess.run("lightning studio switch --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning studio switch [OPTIONS]

  Switch a Studio to a different machine type.

Options:
  --name TEXT                     The name of the studio to switch to a
                                  different machine. If not provided, will try
                                  to infer from environment, use the default
                                  value from the config or prompt for
                                  interactive selection.
  --teamspace TEXT                Override default teamspace (format:
                                  owner/teamspace)
  --machine [CPU_SMALL|CPU|CPU_X_2|CPU_X_4|CPU_X_8|CPU_X_16|DATA_PREP|DATA_PREP_MAX|DATA_PREP_ULTRA|T4_SMALL|T4|T4_X_2|T4_X_4|T4_X_8|L4|L4_X_2|L4_X_4|L4_X_8|L40S|L40S_X_2|L40S_X_4|L40S_X_8|A100|A100_X_2|A100_X_4|A100_X_8|A100_40GB|A100_40GB_X_2|A100_40GB_X_4|A100_40GB_X_8|A100_80GB|A100_80GB_X_2|A100_80GB_X_4|A100_80GB_X_8|H100|H100_X_2|H100_X_4|H100_X_8|H200|H200_X_8|B200_X_8]
                                  The machine type to switch the studio to.
  --interruptible                 Switch the studio to an interruptible
                                  instance.
  --help                          Show this message and exit.
"""  # noqa: E501
    )
