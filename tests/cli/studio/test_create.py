import subprocess


def test_create_studio():
    result = subprocess.run("lightning studio create --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning studio create [OPTIONS]

  Create a new Studio.

  Example:     lightning studio create

Options:
  --name TEXT                     The name of the studio to create. If not
                                  provided, a random name will be generated.
  --teamspace TEXT                Override default teamspace (format:
                                  owner/teamspace)
  --cloud-provider [AWS|GCP|VULTR|LAMBDA_LABS|DGX|VOLTAGE_PARK|NEBIUS|LIGHTNING]
                                  The cloud provider to start the studio on.
                                  Defaults to teamspace default.
  --cloud-account TEXT            The cloud account to create the studio on.
                                  Defaults to teamspace default.
  --help                          Show this message and exit.
"""
    )
