import subprocess


def test_create_vm():
    result = subprocess.run("lightning vm create --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning vm create [OPTIONS]

  Create a new VM.

  Example:     lightning vm create

Options:
  --name TEXT                     The name of the VM to create. If not
                                  provided, a random name will be generated.
  --teamspace TEXT                Override default teamspace (format:
                                  owner/teamspace)
  --cloud-provider [AWS|GCP|LAMBDA_LABS|DGX|VOLTAGE_PARK|NEBIUS|MACHINE|LIGHTNING]
                                  The cloud provider to start the VM on.
                                  Defaults to teamspace default.
  --cloud-account TEXT            The cloud account to create the VM on.
                                  Defaults to teamspace default.
  --help                          Show this message and exit.
"""
    )
