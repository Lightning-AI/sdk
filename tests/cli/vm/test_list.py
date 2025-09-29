import subprocess


def test_list_vm():
    result = subprocess.run("lightning vm list --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning vm list [OPTIONS]

  List VMs in a teamspace.

  Example:     lightning vm list --teamspace owner/teamspace

Options:
  --teamspace TEXT                Override default teamspace (format:
                                  owner/teamspace)
  --all                           List all VMs, not just the ones belonging to
                                  the authed user
  --sort-by [name|teamspace|status|machine|cloud-account]
                                  the attribute to sort the VMs by.
  --help                          Show this message and exit.
"""
    )
