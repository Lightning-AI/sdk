import subprocess


def test_delete_vm():
    result = subprocess.run("lightning vm delete --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning vm delete [OPTIONS]

  Delete a VM.

  Example:   lightning vm delete --name my-vm

Options:
  --name TEXT       The name of the VM to delete. If not provided, will try to
                    infer from environment, use the default value from the
                    config or prompt for interactive selection.
  --teamspace TEXT  Override default teamspace (format: owner/teamspace)
  --help            Show this message and exit.
"""
    )
