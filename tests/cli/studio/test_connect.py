import subprocess

import pytest

from lightning_sdk.cli.studio.connect import (
    _construct_available_gpus,
    _get_machine_from_gpus,
    _split_gpus_spec,
)


def test_connect_studio():
    result = subprocess.run("lightning studio connect --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning studio connect [OPTIONS] [NAME]

  Connect to a Studio.

  Example:     lightning studio connect

Options:
  --teamspace TEXT                Override default teamspace (format:
                                  owner/teamspace)
  --cloud-provider [AWS|GCP|VULTR|LAMBDA_LABS|DGX|VOLTAGE_PARK|NEBIUS|LIGHTNING]
                                  The cloud provider to start the studio on.
                                  Defaults to teamspace default.
  --cloud-account TEXT            The cloud account to create the studio on.
                                  Defaults to teamspace default.
  --machine [CPU_SMALL|CPU|CPU_X_2|CPU_X_4|CPU_X_8|CPU_X_16|DATA_PREP|DATA_PREP_MAX|DATA_PREP_ULTRA|T4|T4_X_2|T4_X_4|T4_X_8|L4|L4_X_2|L4_X_4|L4_X_8|L40S|L40S_X_2|L40S_X_4|L40S_X_8|A100|A100_X_2|A100_X_4|A100_X_8|H100|H100_X_2|H100_X_4|H100_X_8|H200|H200_X_8|B200_X_8]
                                  The machine type to start the studio on.
                                  Defaults to CPU-4
  --gpus TEXT                     The number and type of GPUs to start the
                                  studio on (format: TYPE:COUNT, e.g. L4:4)
  --studio-type TEXT              The base studio template to use for creating
                                  the studio. Defaults to the first available
                                  template.
  --help                          Show this message and exit.
"""  # noqa: E501
    )


def test_split_gpus_spec_valid():
    name, count = _split_gpus_spec("L4:4")
    assert name == "L4"
    assert isinstance(count, int)
    assert count == 4


def test_split_gpus_spec_trims_spaces():
    name, count = _split_gpus_spec("  L4  :  2  ")
    assert name == "L4"
    assert count == 2


@pytest.mark.parametrize("bad", ["L4:0", "L4:-1", "L4:foo"])
def test_split_gpus_spec_invalid_counts(bad):
    with pytest.raises(ValueError, match="Invalid GPU count"):
        _split_gpus_spec(bad)


def test_construct_available_gpus():
    machine_options = {"l4": "L4", "l4_x_4": "L4_X_4", "cpu": "CPU"}
    res = _construct_available_gpus(machine_options)
    assert set(res) == {"L4", "L4:4", "CPU"}


def test_get_machine_from_gpus_simple_and_with_count():
    # simple GPU type
    assert _get_machine_from_gpus("L4") == "L4"
    # explicit single GPU
    assert _get_machine_from_gpus("L4:1") == "L4"
    # multi GPU specification
    assert _get_machine_from_gpus("L4:4") == "L4_X_4"
    # case-insensitive input
    assert _get_machine_from_gpus("l4:2") == "L4_X_2"
    # other types
    assert _get_machine_from_gpus("A100:8") == "A100_X_8"


@pytest.mark.parametrize("bad", ["FOO:1", "UNKNOWN", "A100:999"])
def test_get_machine_from_gpus_invalid(bad):
    with pytest.raises(ValueError, match="Invalid GPU"):
        _get_machine_from_gpus(bad)
