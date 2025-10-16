import subprocess


def test_start_studio():
    result = subprocess.run("lightning studio start --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning studio start [OPTIONS]

  Start a Studio.

  Example:     lightning studio start --name my-studio

Options:
  --name TEXT                     The name of the studio to start. If not
                                  provided, will try to infer from
                                  environment, use the default value from the
                                  config or prompt for interactive selection.
  --teamspace TEXT                Override default teamspace (format:
                                  owner/teamspace)
  --create                        Create the studio if it doesn't exist
  --machine [CPU_SMALL|CPU|CPU_X_2|CPU_X_4|CPU_X_8|CPU_X_16|DATA_PREP|DATA_PREP_MAX|DATA_PREP_ULTRA|T4_SMALL|T4|T4_X_2|T4_X_4|T4_X_8|L4|L4_X_2|L4_X_4|L4_X_8|L40S|L40S_X_2|L40S_X_4|L40S_X_8|A100|A100_X_2|A100_X_4|A100_X_8|H100|H100_X_2|H100_X_4|H100_X_8|H200|H200_X_8|B200_X_8]
                                  The machine type to start the studio on.
                                  Defaults to CPU-4
  --interruptible                 Start the studio on an interruptible
                                  instance.
  --cloud-provider [AWS|GCP|LAMBDA_LABS|DGX|VOLTAGE_PARK|NEBIUS|LIGHTNING]
                                  The cloud provider to start the studio on.
                                  Defaults to teamspace default. Only used if
                                  --create is specified.
  --cloud-account TEXT            The cloud account to start the studio on.
                                  Defaults to teamspace default. Only used if
                                  --create is specified.
  --help                          Show this message and exit.
"""  # noqa: E501
    )
