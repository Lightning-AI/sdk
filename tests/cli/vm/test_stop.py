import subprocess


def test_stop_vm():
    result = subprocess.run("lightning vm stop --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning vm stop [OPTIONS]

  Stop a VM.

  Example:     lightning vm stop --name my-vm

Options:
  --name TEXT       The name of the VM to stop. If not provided, will try to
                    infer from environment, use the default value from the
                    config or prompt for interactive selection.
  --teamspace TEXT  Override default teamspace (format: owner/teamspace)
  --help            Show this message and exit.
"""
    )
