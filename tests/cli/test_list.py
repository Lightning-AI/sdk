import subprocess


def test_list_help():
    result = subprocess.run("lightning list --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning list [OPTIONS] COMMAND [ARGS]...

  List resources on the Lightning AI platform.

Options:
  --help  Show this message and exit.

Commands:
  containers  Display the list of available containers.
  jobs        List jobs for a given teamspace.
  machines    Display the list of available machines.
  mmts        List multi-machine jobs for a given teamspace.
  studios     List studios for a given teamspace.
"""
    )


def test_containers_help():
    result = subprocess.run("lightning list containers --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning list containers [OPTIONS]

  Display the list of available containers.

Options:
  --teamspace TEXT                the teamspace to list containers from.
                                  Should be specified as {owner}/{name}If not
                                  provided, can be selected in an interactive
                                  menu.
  --cloud-account, --cloud_account TEXT
                                  The name of the cloud account where
                                  containers are stored in.
  --help                          Show this message and exit.
"""
    )


def test_jobs_help():
    result = subprocess.run("lightning list jobs --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning list jobs [OPTIONS]

  List jobs for a given teamspace.

Options:
  --teamspace TEXT                the teamspace to list jobs from. Should be
                                  specified as {owner}/{name}If not provided,
                                  can be selected in an interactive menu.
  --all                           if teamspace is not provided, list all jobs
                                  in all teamspaces.
  --sort-by, --sort_by [name|teamspace|status|studio|machine|image|cloud-account]
                                  the attribute to sort the jobs by.
  --help                          Show this message and exit.
"""
    )


def test_machines_help():
    result = subprocess.run("lightning list machines --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning list machines [OPTIONS]

  Display the list of available machines.

Options:
  --help  Show this message and exit.
"""
    )


def test_machines_output():
    result = subprocess.run("lightning list machines", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """┏━━━━━━━━━━━━━━━━━┓
┃ Name            ┃
┡━━━━━━━━━━━━━━━━━┩
│ A100_X_2        │
│ A100_X_4        │
│ A100_X_8        │
│ A10G            │
│ A10G_X_4        │
│ A10G_X_8        │
│ B200_X_8        │
│ CPU             │
│ CPU_SMALL       │
│ DATA_PREP       │
│ DATA_PREP_MAX   │
│ DATA_PREP_ULTRA │
│ H100_X_8        │
│ H200_X_8        │
│ L4              │
│ L40S            │
│ L40S_X_4        │
│ L40S_X_8        │
│ L4_X_2          │
│ L4_X_4          │
│ L4_X_8          │
│ T4              │
│ T4_X_4          │
└─────────────────┘
"""
    )


def test_mmts_help():
    result = subprocess.run("lightning list mmts --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning list mmts [OPTIONS]

  List multi-machine jobs for a given teamspace.

Options:
  --teamspace TEXT                the teamspace to list multi-machine jobs
                                  from. Should be specified as
                                  {owner}/{name}If not provided, can be
                                  selected in an interactive menu.
  --all                           if teamspace is not provided, list all
                                  multi-machine jobs in all teamspaces.
  --sort-by, --sort_by [name|teamspace|studio|image|status|machine|cloud-account]
                                  the attribute to sort the multi-machine jobs
                                  by.
  --help                          Show this message and exit.
"""
    )


def test_studios_help():
    result = subprocess.run("lightning list studios --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning list studios [OPTIONS]

  List studios for a given teamspace.

Options:
  --teamspace TEXT                the teamspace to list studios from. Should
                                  be specified as {owner}/{name}If not
                                  provided, can be selected in an interactive
                                  menu.
  --all                           if teamspace is not provided, list all
                                  studios in all teamspaces.
  --sort-by [name|teamspace|status|machine|cloud-account]
                                  the attribute to sort the studios by.
  --help                          Show this message and exit.
"""
    )
