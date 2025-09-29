import subprocess


def test_ssh_studio():
    result = subprocess.run("lightning studio ssh --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning studio ssh [OPTIONS]

  SSH into a Studio.

  Example:     lightning studio ssh --name my-studio

Options:
  --name TEXT        The name of the studio to ssh into. If not provided, will
                     try to infer from environment, use the default value from
                     the config or prompt for interactive selection.
  --teamspace TEXT   Override default teamspace (format: owner/teamspace)
  -o, --option TEXT  Additional options to pass to the SSH command. Can be
                     specified multiple times.
  --help             Show this message and exit.
"""
    )
