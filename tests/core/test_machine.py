import pytest

from lightning_sdk import Machine


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
        ("L40S_X_4", Machine.L40S_X_4),
        ("L40S_X_8", Machine.L40S_X_8),
        ("A100_X_8", Machine.A100_X_8),
        ("H100_X_8", Machine.H100_X_8),
        ("H200_X_8", Machine.H200_X_8),
    ],
)
def test_machine_equal(machine_str: str, expected_enum: Machine):
    assert getattr(Machine, machine_str) == expected_enum
