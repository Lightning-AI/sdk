import subprocess
from unittest.mock import patch

from click.testing import CliRunner

from lightning_sdk.cli import start as start_cli


def test_start_help():
    result = subprocess.run("lightning start --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning start [OPTIONS] COMMAND [ARGS]...

  Start resources on the Lightning AI platform.

Options:
  --help  Show this message and exit.

Commands:
  studio  Start a studio on a given machine.
"""
    )


def test_studio_help():
    result = subprocess.run("lightning start studio --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning start studio [OPTIONS] NAME

  Start a studio on a given machine.

  Example:   lightning start studio NAME

  NAME: the name of the studio to start

Options:
  --teamspace TEXT                The teamspace the studio is part of. Should
                                  be of format <OWNER>/<TEAMSPACE_NAME>. If
                                  not specified, tries to infer from the
                                  environment (e.g. when run from within a
                                  Studio.)
  --machine [CPU|CPU_SMALL|DATA_PREP|DATA_PREP_MAX|DATA_PREP_ULTRA|T4|T4_X_4|L4|L4_X_2|L4_X_4|L4_X_8|A10G|A10G_X_4|A10G_X_8|L40S|L40S_X_4|L40S_X_8|A100_X_2|A100_X_4|A100_X_8|B200_X_8|H100_X_8|H200_X_8]
                                  The machine type to start the studio on.
                                  [default: CPU]
  --cloud-provider [AWS|GCP|VULTR|LAMBDA_LABS|DGX|VOLTAGE_PARK|NEBIUS|LIGHTNING]
                                  The provider to create the studio on. If
                                  --cloud-account is specified, this option is
                                  prioritized.
  --provider [AWS|GCP|VULTR|LAMBDA_LABS|DGX|VOLTAGE_PARK|NEBIUS|LIGHTNING]
                                  Deprecated. Use --cloud-provider instead.
                                  The provider to create the studio on. If
                                  --cloud-account is specified, this option is
                                  prioritized.
  --help                          Show this message and exit.
"""  # noqa: E501
    )


@patch("lightning_sdk.cli.start.Studio")
def test_start_cli(mock_studio_class):
    mock_studio_instance = mock_studio_class.return_value
    mock_studio_instance.start.side_effect = Exception("Studio not found")

    runner = CliRunner()
    result = runner.invoke(start_cli.studio, ["test", "--teamspace", "aniket/test"])

    assert result.exit_code != 0
    assert "Studio not found" in str(result.exception)
