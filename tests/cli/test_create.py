import subprocess


def test_create_help():
    result = subprocess.run("lightning create --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning create [OPTIONS] COMMAND [ARGS]...

  Create new resources on the Lightning AI platform.

Options:
  --help  Show this message and exit.

Commands:
  studio  Create a new studio on the Lightning AI platform.
"""
    )


def test_studio_help():
    result = subprocess.run("lightning create studio --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning create studio [OPTIONS] NAME

  Create a new studio on the Lightning AI platform.

  Example:     lightning create studio NAME

  NAME: the name of the studio to create. If already present within teamspace,
  will add a random suffix.

Options:
  --teamspace TEXT                The teamspace the studio will be part of.
                                  Should be of format
                                  <OWNER>/<TEAMSPACE_NAME>. If not specified,
                                  tries to infer from the environment (e.g.
                                  when run from within a Studio.)
  --start [CPU|DATA_PREP|DATA_PREP_MAX|DATA_PREP_ULTRA|T4|T4_X_4|L4|L4_X_4|L4_X_8|A10G|A10G_X_4|A10G_X_8|L40S|L40S_X_4|L40S_X_8|A100_X_8|H100_X_8|H200_X_8]
                                  If specified, will start the created studio
                                  on the given machine.
  --cloud-account, --cloud_account TEXT
                                  The cloud account to create the studio on.
                                  If not specified, will try to infer from the
                                  environment (e.g. when run from within a
                                  Studio.) or fall back to the teamspace
                                  default.
  --provider [AWS|GCP|VULTR|LAMBDA_LABS|DGX|VOLTAGE_PARK|NEBIUS|CLOUDFLARE|LIGHTNING]
                                  The provider to create the studio on. If
                                  --cloud-account is specified, this option is
                                  prioritized.
  --help                          Show this message and exit.
"""  # noqa: E501
    )
