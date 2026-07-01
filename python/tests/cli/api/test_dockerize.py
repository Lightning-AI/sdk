import os
from importlib.util import find_spec
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk.cli.legacy.docker_cli import _api as docker_api
from tests.cli.help import assert_help_contains, mock_command_logging

_LLITSERVE_AVAILABLE = find_spec("litserve") is not None


@mock_command_logging
def test_dockerize_help():
    text = assert_help_contains(
        "lightning dockerize --help",
        "`lightning dockerize` has moved to noun-first commands:",
        "api -> lightning api dockerize",
    )
    assert "Deprecation warning:" not in text


@mock_command_logging
def test_api_dockerize_help():
    assert_help_contains(
        "lightning api dockerize --help",
        "Usage: lightning api dockerize",
        "Generate a Dockerfile for the given server code.",
    )


@mock_command_logging
def test_apis_dockerize_help():
    assert_help_contains(
        "lightning apis dockerize --help",
        "Usage: lightning apis dockerize",
        "Generate a Dockerfile for the given server code.",
    )


@mock_command_logging
def test_api_help():
    assert_help_contains(
        "lightning dockerize api --help",
        "Deprecation warning:",
        "Use `lightning api dockerize` instead of `lightning dockerize api`.",
        "Usage: lightning dockerize api [OPTIONS] SERVER_FILE",
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


@pytest.mark.skipif(not _LLITSERVE_AVAILABLE, reason="this test requires optional LitServe dependency")
@mock_command_logging
def test_docker_api_file_not_found(mock_cwd):
    with pytest.raises(FileNotFoundError, match="Server file `server.py` must be in the current directory"):
        docker_api("server.py")


@pytest.mark.skipif(not _LLITSERVE_AVAILABLE, reason="this test requires optional LitServe dependency")
@patch("lightning_sdk.serve.Console")
@mock_command_logging
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


@pytest.mark.skipif(not _LLITSERVE_AVAILABLE, reason="this test requires optional LitServe dependency")
@mock_command_logging
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


@pytest.mark.skipif(not _LLITSERVE_AVAILABLE, reason="this test requires optional LitServe dependency")
@mock_command_logging
def test_docker_api_with_gpu(mock_cwd, temp_script):
    with patch("litserve.__version__", "1.0.0"):
        docker_api("server.py", port=8000, gpu=True)

    assert (mock_cwd / "Dockerfile").exists(), "Dockerfile not generated"
    dockerfile_content = (mock_cwd / "Dockerfile").read_text()
    assert "FROM nvidia/cuda:" in dockerfile_content
    assert 'CMD ["python", "/app/server.py"]' in dockerfile_content


@pytest.mark.skipif(not _LLITSERVE_AVAILABLE, reason="this test requires optional LitServe dependency")
@patch("lightning_sdk.serve.Console")
@mock_command_logging
def test_skip_dockerfile_generation(mock_console, mock_cwd):
    console_obj = MagicMock()
    mock_console.return_value = console_obj
    dockerfile_path = Path(mock_cwd) / "Dockerfile"
    dockerfile_path.touch()

    docker_api("server.py", port=8000, gpu=False)

    console_obj.print.assert_called_with(
        "Dockerfile already exists in the current directory, we will use it for building the container."
    )
