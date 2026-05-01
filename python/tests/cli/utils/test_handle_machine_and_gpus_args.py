import pytest

from lightning_sdk.cli.utils.handle_machine_and_gpus_args import (
    _construct_available_gpus,
    _get_machine_from_gpus,
    _split_gpus_spec,
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
