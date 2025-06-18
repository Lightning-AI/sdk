from unittest.mock import patch

import pytest

from lightning_sdk import Sandbox
from lightning_sdk.machine import Machine
from lightning_sdk.status import Status


@patch("lightning_sdk.sandbox.Studio")
def test_sandbox(mock_studio):
    mock_studio.return_value.run_with_exit_code.return_value = ("Python 3.10.0", 0)
    with Sandbox(teamspace="growth", org="lightning-ai") as sandbox:
        output = sandbox.run("python --version")
        assert output.text == "Python 3.10.0"
        assert output.exit_code == 0


@patch("lightning_sdk.sandbox.Studio")
def test_start(mock_studio):
    mock_studio.return_value.status = Status.NotCreated
    with Sandbox(teamspace="growth", org="lightning-ai"):
        mock_studio.return_value.start.assert_called_once_with(machine=Machine.CPU, interruptible=None)


@patch("lightning_sdk.sandbox.Studio")
def test_start_already_running(mock_studio):
    mock_studio.return_value.status = Status.Running
    with pytest.raises(RuntimeError, match="already running."), Sandbox(
        teamspace="growth", org="lightning-ai"
    ) as sandbox:
        sandbox.run("python --version")


@patch("lightning_sdk.sandbox.Studio")
def test_start_pending(mock_studio):
    mock_studio.return_value.status = Status.Pending
    with pytest.raises(RuntimeError, match="already starting."), Sandbox(
        teamspace="growth", org="lightning-ai"
    ) as sandbox:
        sandbox.run("python --version")


@patch("lightning_sdk.sandbox.Studio")
def test_delete_not_created(mock_studio):
    mock_studio.return_value.status = Status.NotCreated
    with pytest.raises(RuntimeError, match="not created."), Sandbox(teamspace="growth", org="lightning-ai") as sandbox:
        sandbox.delete()
