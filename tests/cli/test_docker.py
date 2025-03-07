import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk.cli.docker import _api as docker_api


def test_dockerize_help():
    result = subprocess.run("lightning dockerize --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning dockerize [OPTIONS] COMMAND [ARGS]...

  Generate a Dockerfile for a LitServe model.

Options:
  --help  Show this message and exit.

Commands:
  api  Generate a Dockerfile for the given server code.
"""
    )


def test_api_help():
    result = subprocess.run("lightning dockerize api --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning dockerize api [OPTIONS] SERVER_FILENAME

  Generate a Dockerfile for the given server code.

Options:
  --port INTEGER  Port to expose in the Docker container.
  --gpu           Use a GPU-enabled Docker image.
  --tag TEXT      Docker image tag to use in examples.
  --help          Show this message and exit.
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
def test_docker_api_file_not_found(mock_cwd):
    with pytest.raises(FileNotFoundError, match="Server file `server.py` must be in the current directory"):
        docker_api("server.py")


@pytest.mark.skipif(sys.version_info < (3, 9), reason="LitServe requires python3.9 or above")
@patch("lightning_sdk.serve.Console")
def test_docker_api_without_requirements(mock_console, mock_cwd, temp_script):
    with patch("litserve.__version__", "1.0.0"):
        docker_api("server.py", port=8000, gpu=False)
    dockerfile_content = (mock_cwd / "Dockerfile").read_text()

    mock_console.assert_called_once()
    assert mock_console.return_value.print.call_count == 2
    assert "requirements.txt not found" in mock_console.return_value.print.call_args_list[0].args[0]
    assert (mock_cwd / "Dockerfile").exists(), "Dockerfile should have been generated"
    assert "ARG PYTHON_VERSION=3.12" in dockerfile_content
    assert "FROM python:$PYTHON_VERSION-slim" in dockerfile_content
    assert 'CMD ["python", "/app/server.py"]' in dockerfile_content


@pytest.mark.skipif(sys.version_info < (3, 9), reason="LitServe requires python3.9 or above")
def test_docker_api_with_requirements(mock_cwd, temp_script):
    requirements_path = Path(mock_cwd) / "requirements.txt"
    requirements_path.touch()

    with patch("litserve.__version__", "1.0.0"):
        docker_api("server.py", port=8000, gpu=False)

    assert (mock_cwd / "Dockerfile").exists(), "Dockerfile not generated"
    dockerfile_content = (mock_cwd / "Dockerfile").read_text()
    assert "ARG PYTHON_VERSION=3.12" in dockerfile_content
    assert "FROM python:$PYTHON_VERSION-slim" in dockerfile_content
    assert "-r requirements.txt" in dockerfile_content
    assert 'CMD ["python", "/app/server.py"]' in dockerfile_content


@pytest.mark.skipif(sys.version_info < (3, 9), reason="LitServe requires python3.9 or above")
def test_docker_api_with_gpu(mock_cwd, temp_script):
    with patch("litserve.__version__", "1.0.0"):
        docker_api("server.py", port=8000, gpu=True)

    assert (mock_cwd / "Dockerfile").exists(), "Dockerfile not generated"
    dockerfile_content = (mock_cwd / "Dockerfile").read_text()
    assert "FROM nvidia/cuda:" in dockerfile_content
    assert 'CMD ["python", "/app/server.py"]' in dockerfile_content


@pytest.mark.skipif(sys.version_info < (3, 9), reason="LitServe requires python3.9 or above")
@patch("lightning_sdk.serve.Console")
def test_skip_dockerfile_generation(mock_console, mock_cwd):
    console_obj = MagicMock()
    mock_console.return_value = console_obj
    dockerfile_path = Path(mock_cwd) / "Dockerfile"
    dockerfile_path.touch()

    docker_api("server.py", port=8000, gpu=False)

    console_obj.print.assert_called_with(
        "Dockerfile already exists in the current directory, we will use it for building the container."
    )
