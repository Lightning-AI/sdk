from unittest.mock import patch

from lightning_sdk import Sandbox


@patch("lightning_sdk.sandbox.Studio")
def test_sandbox(mock_studio):
    mock_studio.return_value.run_with_exit_code.return_value = ("Python 3.10.0", 0)
    with Sandbox(teamspace="growth", org="lightning-ai") as sandbox:
        output = sandbox.run("python --version")
        assert output.text == "Python 3.10.0"
        assert output.exit_code == 0
