import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
import rich

from lightning_sdk.cli.serve import _handle_cloud
from lightning_sdk.cli.serve import api_impl as serve_api


def test_serve_help():
    result = subprocess.run("lightning serve --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning serve [OPTIONS] COMMAND [ARGS]...

  Serve a LitServe model.

  Example:     lightning serve api server.py  # serve locally

  Example:     lightning serve api server.py --cloud --name litserve-api  #
  deploy to the cloud

  You can deploy the API to the cloud by running `lightning serve api
  server.py --cloud`. This will build a docker container for the server.py
  script and deploy it to the Lightning AI platform.

Options:
  --help  Show this message and exit.

Commands:
  api  Deploy a LitServe model script.
"""
    )


def test_api_help():
    result = subprocess.run("lightning serve api --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning serve api [OPTIONS] SCRIPT_PATH

  Deploy a LitServe model script.

Options:
  --easy                          Generate a client for the model
  --cloud                         Deploy the model to the Lightning AI
                                  platform
  --name TEXT                     Name of the deployed API (e.g.,
                                  'classification-api', 'Llama-api')
  --non-interactive, --non_interactive
                                  Do not prompt for confirmation
  --machine [CPU_SMALL|CPU|DATA_PREP|DATA_PREP_MAX|DATA_PREP_ULTRA|T4|T4_X_4|L4|L4_X_4|L4_X_8|A10G|A10G_X_4|A10G_X_8|L40S|L40S_X_4|L40S_X_8|A100_X_8|H100_X_8|H200_X_8]
                                  The machine type to deploy the API on.
                                  [default: CPU]
  --interruptible                 Whether the machine should be interruptible
                                  (spot) or not.
  --teamspace TEXT                The teamspace the deployment should be
                                  associated with. Defaults to the current
                                  teamspace.
  --org TEXT                      The organization owning the teamspace (if
                                  any). Defaults to the current organization.
  --user TEXT                     The user owning the teamspace (if any).
                                  Defaults to the current user.
  --cloud-account, --cloud_account TEXT
                                  The cloud account to run the deployment on.
                                  Defaults to the studio cloud account if
                                  running with studio compute env. If not
                                  provided will fall back to the teamspaces
                                  default cloud account.
  --port INTEGER                  The port to expose the API on.
  --min_replica, --min-replica INTEGER
                                  Number of replicas to start with.
  --max_replica, --max-replica INTEGER
                                  Number of replicas to scale up to.
  --replicas, --replicas INTEGER  Deployment will start with this many
                                  replicas.
  --no_credentials, --no-credentials
                                  Whether to include credentials in the
                                  deployment.
  --help                          Show this message and exit.
"""  # noqa: E501
    )


@pytest.fixture()
def mock_cwd(tmp_path):
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(original_cwd)


@pytest.fixture()
def temp_script(mock_cwd):
    script_path = Path(mock_cwd) / "server.py"
    script_path.write_text(
        """import litserve as ls
if __name__ == "__main__":
    server = ls.LitServer(ls.test_examples.SimpleLitAPI())
    server.run(port=8000)"""
    )
    return script_path


@pytest.mark.skipif(sys.version_info < (3, 9), reason="LitServe requires python3.9 or above")
@patch("subprocess.run")
def test_api_with_easy_mode(mock_subprocess, mock_cwd, temp_script):
    serve_api(temp_script, True)

    assert (mock_cwd / "client.py").exists(), "Client file not generated"
    mock_subprocess.assert_called_once_with(
        ["python", str(temp_script)],
        check=True,
        text=True,
    )


@pytest.mark.skipif(sys.version_info < (3, 9), reason="LitServe requires python3.9 or above")
@patch("docker.from_env")
@patch("rich.prompt.Confirm.ask")
@patch("lightning_sdk.cli.serve._TeamspacesMenu")
@patch("lightning_sdk.cli.serve.LitContainerApi")
@patch("lightning_sdk.cli.serve.DeploymentApi")
@patch("lightning_sdk.serve._LitServeDeployer._run_on_cloud")
@patch("lightning_sdk.serve._LitServeDeployer._docker_build_with_logs")
def test_cloud_deployment(
    mock_docker_build,
    mock_run_on_cloud,
    mock_deploy_api,
    mock_litcr,
    mock_teamspace,
    mock_confirm,
    mock_docker,
    mock_cwd,
    temp_script,
    capsys,
):
    mock_client = mock_docker.return_value

    # Mock Docker client responses
    mock_client.ping.return_value = True
    mock_client.api.build.return_value = [{"stream": "Step 1/10"}]
    mock_client.api.push.return_value = [{"status": "Pushing"}]

    # Mock user confirmations
    mock_confirm.side_effect = [
        True,  # "Would you like to deploy this model to the cloud?"
        True,  # "Is the Dockerfile correct?"
    ]

    # Test with specific repository tag
    repo = "test-repo/model"
    tag = "latest"
    mock_deploy_api.return_value.get_deployment_by_name.return_value = None
    serve_api(temp_script, cloud=True, repository=repo, tag=tag)

    mock_teamspace.return_value._resolve_teamspace.assert_called_once()

    # Verify Docker operations
    mock_docker_build.assert_called_once()
    mock_litcr.return_value.upload_container.assert_called_once()

    # Verify user was prompted twice
    assert mock_confirm.call_count == 1
    mock_confirm.assert_has_calls([call("Is the Dockerfile correct?", default=True)])

    # Capture and verify the output
    captured = capsys.readouterr()
    assert f"✅ Image pushed to {repo}" in captured.out


@pytest.mark.skipif(sys.version_info < (3, 9), reason="LitServe requires python3.9 or above")
@patch("docker.from_env")
@patch("rich.prompt.Confirm.ask")
@patch("lightning_sdk.cli.serve._TeamspacesMenu")
@patch("lightning_sdk.cli.serve.LitContainerApi")
@patch("lightning_sdk.cli.serve.DeploymentApi")
@patch("lightning_sdk.serve._LitServeDeployer._run_on_cloud")
@patch("lightning_sdk.serve._LitServeDeployer._docker_build_with_logs")
def test_cloud_deployment_non_interactive(
    mock_docker_build,
    mock_run_cloud,
    mock_deployment_api,
    mock_litcr,
    mock_teamspace,
    mock_confirm,
    mock_docker,
    mock_cwd,
    temp_script,
    capsys,
):
    mock_client = mock_docker.return_value

    # Mock Docker client responses
    mock_client.ping.return_value = True
    mock_client.api.build.return_value = [{"stream": "Step 1/10"}]
    mock_client.api.push.return_value = [{"status": "Pushing"}]

    repo = "test-repo/model"
    tag = "latest"
    mock_deployment_api.return_value.get_deployment_by_name.return_value = None
    serve_api(temp_script, cloud=True, repository=repo, tag=tag, non_interactive=True)

    mock_teamspace.return_value._resolve_teamspace.assert_called_once()

    mock_deployment_api.return_value.get_deployment_by_name.assert_called_once()

    mock_docker_build.assert_called_once()
    mock_litcr.return_value.upload_container.assert_called_once()

    assert mock_confirm.call_count == 0
    captured = capsys.readouterr()
    assert f"✅ Image pushed to {repo}:{tag}" in captured.out


@patch("lightning_sdk.cli.serve.datetime")
@patch("lightning_sdk.cli.serve.subprocess.run")
def test_args_with_repository(mock_subprocess, mock_dt, temp_script):
    serve_api(temp_script, repository="test")
    mock_dt.now.assert_not_called()
    mock_subprocess.assert_called_once()


@patch("lightning_sdk.cli.serve.datetime")
@patch("lightning_sdk.cli.serve.subprocess.run")
def test_args_without_repository(mock_subprocess, mock_dt, temp_script):
    serve_api(temp_script)
    mock_dt.now.assert_called()
    mock_subprocess.assert_called_once()


@patch("lightning_sdk.cli.serve.LitContainerApi")
@patch("lightning_sdk.cli.serve.Teamspace")
@patch("lightning_sdk.cli.serve._LitServeDeployer")
@patch("lightning_sdk.cli.serve.Confirm.ask")
@patch("lightning_sdk.cli.serve.DeploymentApi")
def test_handle_cloud(mock_deployment_api, mock_ask, mock_ls_deployer, mock_teamspace, mock_litcr, temp_script):
    mock_ask.return_value = True
    mock_deployment_api.return_value.get_deployment_by_name.return_value = None
    console = rich.console.Console()
    _handle_cloud(
        temp_script,
        console,
        teamspace="test",
        machine=MagicMock(),
    )
    mock_litcr.assert_called_once()
    mock_litcr.return_value.list_containers.assert_called_once()
    mock_ls_deployer.return_value.push_container.assert_called_once()
    mock_ls_deployer.assert_called_once()
