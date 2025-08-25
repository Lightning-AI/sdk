import subprocess


def test_inspect_help():
    result = subprocess.run("lightning inspect --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning inspect [OPTIONS] COMMAND [ARGS]...

  Inspect resources of the Lightning AI platform to get additional details as
  JSON.

Options:
  --help  Show this message and exit.

Commands:
  job  Inspect a job for further details as JSON.
  mmt  Inspect a multi-machine job for further details as JSON.
"""
    )


def test_job_help():
    result = subprocess.run("lightning inspect job --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning inspect job [OPTIONS]

  Inspect a job for further details as JSON.

Options:
  --name TEXT       the name of the job. If not specified can be selected
                    interactively.
  --teamspace TEXT  the name of the teamspace the job lives in.Should be
                    specified as {teamspace_owner}/{teamspace_name} (e.g my-
                    org/my-teamspace). If not specified can be selected
                    interactively.
  --help            Show this message and exit.
"""
    )


def test_mmt_help():
    result = subprocess.run("lightning inspect mmt --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning inspect mmt [OPTIONS]

  Inspect a multi-machine job for further details as JSON.

Options:
  --name TEXT       the name of the job. If not specified can be selected
                    interactively.
  --teamspace TEXT  the name of the teamspace the job lives in.Should be
                    specified as {teamspace_owner}/{teamspace_name} (e.g my-
                    org/my-teamspace). If not specified can be selected
                    interactively.
  --help            Show this message and exit.
"""
    )
