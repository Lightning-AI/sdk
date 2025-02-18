import subprocess


def test_stop_help():
    result = subprocess.run("lightning stop --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning stop [OPTIONS] COMMAND [ARGS]...

  Stop resources on the Lightning AI platform.

Options:
  --help  Show this message and exit.

Commands:
  job     Stop a job.
  mmt     Stop a multi-machine job.
  studio  Stop a running studio.
"""
    )


def test_job_help():
    result = subprocess.run("lightning stop job --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning stop job [OPTIONS]

  Stop a job.

Options:
  --name TEXT       the name of the job. If not specified can be selected
                    interactively.
  --teamspace TEXT  the name of the teamspace the job lives in. Should be
                    specified as {teamspace_owner}/{teamspace_name} (e.g my-
                    org/my-teamspace). If not specified can be selected
                    interactively.
  --help            Show this message and exit.
"""
    )


def test_mmt_help():
    result = subprocess.run("lightning stop mmt --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning stop mmt [OPTIONS]

  Stop a multi-machine job.

Options:
  --name TEXT       the name of the multi-machine job. If not specified can be
                    selected interactively.
  --teamspace TEXT  the name of the teamspace the multi-machine job lives in.
                    Should be specified as {teamspace_owner}/{teamspace_name}
                    (e.g my-org/my-teamspace). If not specified can be
                    selected interactively.
  --help            Show this message and exit.
"""
    )


def test_studio_help():
    result = subprocess.run("lightning stop studio --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning stop studio [OPTIONS] NAME

  Stop a running studio.

  Example:   lightning stop studio NAME

  NAME: the name of the studio to stop.

Options:
  --teamspace TEXT  the name of the teamspace the studio lives in. Should be
                    specified as {teamspace_owner}/{teamspace_name} (e.g my-
                    org/my-teamspace). If not specified can be selected
                    interactively.
  --help            Show this message and exit.
"""
    )
