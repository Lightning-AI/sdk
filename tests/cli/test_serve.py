import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import call, patch

import pytest

from lightning_sdk.cli.serve import api_impl as serve_api


def test_serve_help():
    result = subprocess.run("lightning serve --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning serve [OPTIONS] COMMAND [ARGS]...

  Serve a LitServe model.

  Example:     lightning serve api server.py  # serve locally

  Example:     lightning serve api server.py --cloud  # deploy to the cloud

  You can deploy the API to the cloud by running `lightning serve api
  server.py --cloud`. This will generate a Dockerfile, build the image, and
  push it to the image registry. Deploying to the cloud requires pre-login to
  the docker registry.

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
  --gpu                           Use GPU for serving
  --repository TEXT               Docker repository name (e.g.,
                                  'username/model-name')
  --non-interactive, --non_interactive
                                  Do not prompt for confirmation
  --help                          Show this message and exit.
"""
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
def test_cloud_deployment(mock_confirm, mock_docker, mock_cwd, temp_script, capsys):
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
    test_tag = "test-repo/model:latest"
    serve_api(temp_script, cloud=True, repository=test_tag)

    # Verify Docker operations
    mock_client.ping.assert_called_once()
    mock_client.api.build.assert_called_once()
    mock_client.api.push.assert_called_once()

    # Verify user was prompted twice
    assert mock_confirm.call_count == 1
    mock_confirm.assert_has_calls([call("Is the Dockerfile correct?", default=True)])

    # Capture and verify the output
    captured = capsys.readouterr()
    assert f"✅ Image pushed to {test_tag}" in captured.out


@pytest.mark.skipif(sys.version_info < (3, 9), reason="LitServe requires python3.9 or above")
@patch("docker.from_env")
@patch("rich.prompt.Confirm.ask")
def test_cloud_deployment_non_interactive(mock_confirm, mock_docker, mock_cwd, temp_script, capsys):
    mock_client = mock_docker.return_value

    # Mock Docker client responses
    mock_client.ping.return_value = True
    mock_client.api.build.return_value = [{"stream": "Step 1/10"}]
    mock_client.api.push.return_value = [{"status": "Pushing"}]

    test_tag = "test-repo/model:latest"
    serve_api(temp_script, cloud=True, repository=test_tag, non_interactive=True)

    mock_client.ping.assert_called_once()
    mock_client.api.build.assert_called_once()
    mock_client.api.push.assert_called_once()

    assert mock_confirm.call_count == 0
    captured = capsys.readouterr()
    assert f"✅ Image pushed to {test_tag}" in captured.out


@pytest.mark.skipif(sys.version_info < (3, 9), reason="LitServe requires python3.9 or above")
@patch("docker.from_env")
def test_cloud_deployment_no_docker(mock_docker, temp_script):
    mock_docker.side_effect = ImportError("docker-py is not installed")

    with pytest.raises(ImportError, match="docker-py is not installed"):
        serve_api(temp_script, cloud=True)
