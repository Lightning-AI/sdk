import subprocess


def test_help():
    result = subprocess.run("lightning --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning [OPTIONS] COMMAND [ARGS]...

  Command line interface (CLI) to interact with/manage Lightning AI Studios.

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  aihub        Interact with Lightning Studio - AI Hub.
  base-studio  Manage Lightning AI Base Studios.
  config       Manage Lightning SDK and CLI configuration.
  configure    Configure access to resources on the Lightning AI platform.
  connect      Connect to lightning products.
  create       Create new resources on the Lightning AI platform.
  delete       Delete resources on the Lightning AI platform.
  deploy       Deploy a LitServe model.
  dockerize    Generate a Dockerfile for a LitServe model.
  download     Download resources from Lightning AI.
  generate     Generate configs (such as ssh for studio) and print them...
  inspect      Inspect resources of the Lightning AI platform to get...
  license      Manage Lightning AI Product Licenses.
  list         List resources on the Lightning AI platform.
  login        Login to Lightning AI Studios.
  logout       Logout from Lightning AI Studios.
  open         Open a local file or folder in a Lightning Studio.
  run          Run async workloads on the Lightning AI platform.
  start        Start resources on the Lightning AI platform.
  stop         Stop resources on the Lightning AI platform.
  studio       Manage Lightning AI Studios.
  switch       Switch machines for resources on the Lightning AI platform.
  upload       Upload assets to Lightning AI.
  vm           Manage Lightning AI VMs.
"""
    )


def test_help_uvx():
    result = subprocess.run("uvx --with-editable=../ lightning-sdk --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        """Usage: lightning-sdk [OPTIONS] COMMAND [ARGS]...

  Command line interface (CLI) to interact with/manage Lightning AI Studios.

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  aihub        Interact with Lightning Studio - AI Hub.
  base-studio  Manage Lightning AI Base Studios.
  config       Manage Lightning SDK and CLI configuration.
  configure    Configure access to resources on the Lightning AI platform.
  connect      Connect to lightning products.
  create       Create new resources on the Lightning AI platform.
  delete       Delete resources on the Lightning AI platform.
  deploy       Deploy a LitServe model.
  dockerize    Generate a Dockerfile for a LitServe model.
  download     Download resources from Lightning AI.
  generate     Generate configs (such as ssh for studio) and print them...
  inspect      Inspect resources of the Lightning AI platform to get...
  license      Manage Lightning AI Product Licenses.
  list         List resources on the Lightning AI platform.
  login        Login to Lightning AI Studios.
  logout       Logout from Lightning AI Studios.
  open         Open a local file or folder in a Lightning Studio.
  run          Run async workloads on the Lightning AI platform.
  start        Start resources on the Lightning AI platform.
  stop         Stop resources on the Lightning AI platform.
  studio       Manage Lightning AI Studios.
  switch       Switch machines for resources on the Lightning AI platform.
  upload       Upload assets to Lightning AI.
  vm           Manage Lightning AI VMs.
"""
        in result_text  # can't check for equal as the installation logs are in there as well
    )
