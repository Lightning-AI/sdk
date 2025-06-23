from unittest.mock import patch

import pytest

from lightning_sdk.machine import Machine
from lightning_sdk.sandbox import Output, _Sandbox
from lightning_sdk.status import Status


@patch("lightning_sdk.sandbox.Studio")
def test_sandbox(mock_studio):
    mock_studio.return_value.run_with_exit_code.return_value = ("Python 3.10.0", 0)
    with _Sandbox(teamspace="growth", org="lightning-ai") as sandbox:
        output = sandbox.run("python --version")
        assert output.text == "Python 3.10.0"
        assert output.exit_code == 0


@patch("lightning_sdk.sandbox.Studio")
@patch("lightning_sdk.sandbox._Sandbox.run", return_value=Output(text="hello world", exit_code=0))
def test_run_python_code(mock_run, mock_studio):
    with _Sandbox(teamspace="growth", org="lightning-ai") as sandbox:
        output = sandbox.run_python_code("print('hello world')")
        assert output.text == "hello world"
        assert output.exit_code == 0


@patch("lightning_sdk.sandbox.Studio")
def test_start(mock_studio):
    mock_studio.return_value.status = Status.NotCreated
    with _Sandbox(teamspace="growth", org="lightning-ai"):
        mock_studio.return_value.start.assert_called_once_with(machine=Machine.CPU, interruptible=None)


@patch("lightning_sdk.sandbox.Studio")
def test_start_already_running(mock_studio):
    mock_studio.return_value.status = Status.Running
    with pytest.raises(RuntimeError, match="already running."), _Sandbox(
        teamspace="growth", org="lightning-ai"
    ) as sandbox:
        sandbox.run("python --version")


@patch("lightning_sdk.sandbox.Studio")
def test_start_pending(mock_studio):
    mock_studio.return_value.status = Status.Pending
    with pytest.raises(RuntimeError, match="already starting."), _Sandbox(
        teamspace="growth", org="lightning-ai"
    ) as sandbox:
        sandbox.run("python --version")


@patch("lightning_sdk.sandbox.Studio")
def test_delete_not_created(mock_studio):
    mock_studio.return_value.status = Status.NotCreated
    with pytest.raises(RuntimeError, match="not created."), _Sandbox(teamspace="growth", org="lightning-ai") as sandbox:
        sandbox.delete()


def test_validate_python_code():
    with pytest.raises(ValueError, match="Code cannot be empty or only whitespace"):
        _Sandbox._validate_python_code("")

    with pytest.raises(SyntaxError, match="Invalid Python syntax"):
        _Sandbox._validate_python_code("for i in range(10): print(i) if i == 5: print('five')")
