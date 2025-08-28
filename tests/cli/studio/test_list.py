import subprocess


def test_list_studio():
    result = subprocess.run("lightning studio list --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning studio list [OPTIONS]

  List Studios in a teamspace.

  Example:     lightning studio list --teamspace owner/teamspace

Options:
  --teamspace TEXT                Override default teamspace (format:
                                  owner/teamspace)
  --all                           List all studios, not just the ones
                                  belonging to the authed user
  --sort-by [name|teamspace|status|machine|cloud-account]
                                  the attribute to sort the studios by.
  --help                          Show this message and exit.
"""
    )
