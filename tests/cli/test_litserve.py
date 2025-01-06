import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from lightning_sdk.cli.serve import _Docker, _LitServe


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
def test_api_without_litserve(temp_script):
    lit_serve = _LitServe()
    with patch.dict("sys.modules", {"litserve": None}), pytest.raises(ImportError, match="litserve is not installed"):
        lit_serve.api(temp_script)


@pytest.mark.skipif(sys.version_info < (3, 9), reason="LitServe requires python3.9 or above")
@patch("subprocess.run")
def test_api_with_easy_mode(mock_subprocess, mock_cwd, temp_script):
    lit_serve = _LitServe()
    lit_serve.api(temp_script, easy=True)

    assert (mock_cwd / "client.py").exists(), "Client file not generated"
    mock_subprocess.assert_called_once_with(
        ["python", str(temp_script)],
        check=True,
        text=True,
    )


@pytest.mark.skipif(sys.version_info < (3, 9), reason="LitServe requires python3.9 or above")
def test_docker_api_file_not_found(mock_cwd):
    docker = _Docker()
    with pytest.raises(FileNotFoundError, match="Server file `server.py` must be in the current directory"):
        docker.api("server.py")


@pytest.mark.skipif(sys.version_info < (3, 9), reason="LitServe requires python3.9 or above")
def test_docker_api_without_requirements(mock_cwd, temp_script):
    docker = _Docker()
    with patch("litserve.__version__", "1.0.0"), patch("warnings.warn") as mock_warn:
        docker.api("server.py", port=8000, gpu=False)

    mock_warn.assert_called_once()
    assert "requirements.txt not found" in mock_warn.call_args[0][0]

    assert (mock_cwd / "Dockerfile").exists(), "Dockerfile not generated"
    dockerfile_content = (mock_cwd / "Dockerfile").read_text()
    assert "ARG PYTHON_VERSION=3.12" in dockerfile_content
    assert "FROM python:$PYTHON_VERSION-slim" in dockerfile_content
    assert 'CMD ["python", "/app/server.py"]' in dockerfile_content


@pytest.mark.skipif(sys.version_info < (3, 9), reason="LitServe requires python3.9 or above")
def test_docker_api_with_requirements(mock_cwd, temp_script):
    docker = _Docker()
    requirements_path = Path(mock_cwd) / "requirements.txt"
    requirements_path.touch()

    with patch("litserve.__version__", "1.0.0"):
        docker.api("server.py", port=8000, gpu=False)

    assert (mock_cwd / "Dockerfile").exists(), "Dockerfile not generated"
    dockerfile_content = (mock_cwd / "Dockerfile").read_text()
    assert "ARG PYTHON_VERSION=3.12" in dockerfile_content
    assert "FROM python:$PYTHON_VERSION-slim" in dockerfile_content
    assert "-r requirements.txt" in dockerfile_content
    assert 'CMD ["python", "/app/server.py"]' in dockerfile_content


@pytest.mark.skipif(sys.version_info < (3, 9), reason="LitServe requires python3.9 or above")
def test_docker_api_with_gpu(mock_cwd, temp_script):
    docker = _Docker()

    with patch("litserve.__version__", "1.0.0"):
        docker.api("server.py", port=8000, gpu=True)

    assert (mock_cwd / "Dockerfile").exists(), "Dockerfile not generated"
    dockerfile_content = (mock_cwd / "Dockerfile").read_text()
    assert "FROM nvidia/cuda:" in dockerfile_content
    assert 'CMD ["python", "/app/server.py"]' in dockerfile_content
