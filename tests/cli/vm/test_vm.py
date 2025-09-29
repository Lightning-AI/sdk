import subprocess


def test_vm_help():
    result = subprocess.run("lightning vm --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning vm [OPTIONS] COMMAND [ARGS]...

  Manage Lightning AI VMs.

Options:
  --help  Show this message and exit.

Commands:
  create  Create a new VM.
  delete  Delete a VM.
  list    List VMs in a teamspace.
  ssh     SSH into a VM.
  start   Start a VM.
  stop    Stop a VM.
  switch  Switch a VM to a different machine type.
"""
    )
