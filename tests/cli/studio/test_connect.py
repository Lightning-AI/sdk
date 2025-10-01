import subprocess


def test_connect_studio():
    result = subprocess.run("lightning studio connect --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning studio connect [OPTIONS] [NAME]

  Connect to a Studio.

  Example:     lightning studio connect

Options:
  --teamspace TEXT                Override default teamspace (format:
                                  owner/teamspace)
  --cloud-provider [AWS|GCP|VULTR|LAMBDA_LABS|DGX|VOLTAGE_PARK|NEBIUS|LIGHTNING]
                                  The cloud provider to start the studio on.
                                  Defaults to teamspace default.
  --cloud-account TEXT            The cloud account to create the studio on.
                                  Defaults to teamspace default.
  --gpus TEXT                     The number and type of GPUs to start the
                                  studio on (format: TYPE:COUNT, e.g. L4:4)
  --studio-type TEXT              The base studio template to use for creating
                                  the studio. Defaults to the first available
                                  template.
  --help                          Show this message and exit.
"""
    )
