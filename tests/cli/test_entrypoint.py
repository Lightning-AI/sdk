import subprocess


def test_help():
    result = subprocess.run("lightning --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning [OPTIONS] COMMAND [ARGS]...

  Command line interface (CLI) to interact with/manage Lightning AI Studios.

Options:
  --help  Show this message and exit.

Commands:
  aihub      Interact with Lightning Studio - AI Hub.
  configure  Configure access to resources on the Lightning AI platform.
  connect    Connect to lightning products.
  create     Create new resources on the Lightning AI platform.
  delete     Delete resources on the Lightning AI platform.
  dockerize  Generate a Dockerfile for a LitServe model.
  download   Download resources from Lightning AI.
  generate   Generate configs (such as ssh for studio) and print them to...
  inspect    Inspect resources of the Lightning AI platform to get...
  list       List resources on the Lightning AI platform.
  login      Login to Lightning AI Studios.
  logout     Logout from Lightning AI Studios.
  run        Run async workloads on the Lightning AI platform.
  serve      Serve a LitServe model.
  start      Start resources on the Lightning AI platform.
  stop       Stop resources on the Lightning AI platform.
  switch     Switch machines for resources on the Lightning AI platform.
  upload     Upload assets to Lightning AI.
"""
    )
