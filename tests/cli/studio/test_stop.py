import subprocess


def test_stop_studio():
    result = subprocess.run("lightning studio stop --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning studio stop [OPTIONS]

  Stop a Studio.

  Example:     lightning studio stop --name my-studio

Options:
  --name TEXT       The name of the studio to start. If not provided, will try
                    to infer from environment, use the default value from the
                    config or prompt for interactive selection.
  --teamspace TEXT  Override default teamspace (format: owner/teamspace)
  --help            Show this message and exit.
"""
    )
