import pytest

from lightning_sdk import Machine
from lightning_sdk.api.utils import _MACHINE_TO_COMPUTE_NAME


@pytest.mark.parametrize(
    ("deprecated", "new_machine"),
    [
        ("L40", "L40S"),
        ("L40_X_4", "L40S_X_4"),
        ("L40_X_8", "L40S_X_8"),
    ],
)
def test_deprecation(deprecated, new_machine):
    with pytest.warns(
        DeprecationWarning, match=f"Machine.{deprecated} is deprecated. Use Machine.{new_machine} instead."
    ):
        old_machine_value = getattr(Machine, deprecated)

    new_machine_value = getattr(Machine, new_machine)

    assert old_machine_value == new_machine_value


@pytest.mark.parametrize(
    "deprecated_machine",
    [
        "L40",
        "L40_X_4",
        "L40_X_8",
    ],
)
def test_get_machine_deprecated(deprecated_machine):
    # only important thing here is to not get an error
    _MACHINE_TO_COMPUTE_NAME[getattr(Machine, deprecated_machine)]


@pytest.mark.parametrize(
    ("machine_str", "expected_enum"),
    [
        ("CPU_SMALL", Machine.CPU_SMALL),
        ("CPU", Machine.CPU),
        ("DATA_PREP", Machine.DATA_PREP),
        ("DATA_PREP_MAX", Machine.DATA_PREP_MAX),
        ("DATA_PREP_ULTRA", Machine.DATA_PREP_ULTRA),
        ("T4", Machine.T4),
        ("T4_X_4", Machine.T4_X_4),
        ("L4", Machine.L4),
        ("L4_X_4", Machine.L4_X_4),
        ("L4_X_8", Machine.L4_X_8),
        ("A10G", Machine.A10G),
        ("A10G_X_4", Machine.A10G_X_4),
        ("A10G_X_8", Machine.A10G_X_8),
        ("L40S", Machine.L40S),
        ("L40", Machine.L40S),  # deprecated
        ("L40S_X_4", Machine.L40S_X_4),
        ("L40_X_4", Machine.L40S_X_4),  # deprecated
        ("L40S_X_8", Machine.L40S_X_8),
        ("L40_X_8", Machine.L40S_X_8),  # deprecated
        ("A100_X_8", Machine.A100_X_8),
        ("H100_X_8", Machine.H100_X_8),
        ("H200_X_8", Machine.H200_X_8),
    ],
)
def test_get_machine_from_string(machine_str: str, expected_enum: Machine):
    assert Machine[machine_str] == expected_enum
