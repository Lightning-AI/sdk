import subprocess


def test_delete_help():
    result = subprocess.run("lightning delete --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning delete [OPTIONS] COMMAND [ARGS]...

  Delete resources on the Lightning AI platform.

Options:
  --help  Show this message and exit.

Commands:
  container  Delete the docker container CONTAINER.
  job        Delete a job.
  mmt        Delete a multi-machine job.
  studio     Delete an existing studio.
"""
    )


def test_container_help():
    result = subprocess.run("lightning delete container --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning delete container [OPTIONS] CONTAINER

  Delete the docker container CONTAINER.

Options:
  --teamspace TEXT  The teamspace to delete the container from. Should be
                    specified as {owner}/{name} If not provided, can be
                    selected in an interactive menu.
  --help            Show this message and exit.
"""
    )


def test_job_help():
    result = subprocess.run("lightning delete job --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning delete job [OPTIONS]

  Delete a job.

Options:
  --name TEXT       The name of the job to delete.
  --teamspace TEXT  The teamspace to delete the job from. Should be specified
                    as {owner}/{name} If not provided, can be selected in an
                    interactive menu.
  --help            Show this message and exit.
"""
    )


def test_mmt_help():
    result = subprocess.run("lightning delete mmt --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning delete mmt [OPTIONS]

  Delete a multi-machine job.

Options:
  --name TEXT       The name of the multi-machine job to delete.
  --teamspace TEXT  The teamspace to delete the job from. Should be specified
                    as {owner}/{name} If not provided, can be selected in an
                    interactive menu.
  --help            Show this message and exit.
"""
    )


def test_studio_help():
    result = subprocess.run("lightning delete studio --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning delete studio [OPTIONS] NAME

  Delete an existing studio.

  Example:   lightning delete studio NAME

  NAME: the name of the studio to delete

Options:
  --teamspace TEXT  The teamspace to delete the studio from. Should be
                    specified as {owner}/{name} If not provided, can be
                    selected in an interactive menu.
  --help            Show this message and exit.
"""
    )
