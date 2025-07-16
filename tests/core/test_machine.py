import pytest

from lightning_sdk import Machine


@pytest.mark.parametrize(
    ("machine_str", "expected_enum"),
    [
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
        ("CPU_SMALL", Machine.CPU_SMALL),
        ("L4_X_2", Machine.L4_X_2),
        ("A100_X_2", Machine.A100_X_2),
        ("A100_X_4", Machine.A100_X_4),
        ("B200_X_8", Machine.B200_X_8),
    ],
)
def test_machine_equal(machine_str: str, expected_enum: Machine):
    assert getattr(Machine, machine_str) == expected_enum


@pytest.mark.parametrize(
    ("machine_str", "expected_cls_value"),
    [
        # existing instance types
        ("CPU", Machine.CPU),
        ("cpu-4", Machine.CPU),
        ("DATA_PREP", Machine.DATA_PREP),
        ("data-large", Machine.DATA_PREP),
        ("DATA_PREP_MAX", Machine.DATA_PREP_MAX),
        ("data-max", Machine.DATA_PREP_MAX),
        ("DATA_PREP_ULTRA", Machine.DATA_PREP_ULTRA),
        ("data-ultra", Machine.DATA_PREP_ULTRA),
        ("T4", Machine.T4),
        ("g4dn.2xlarge", Machine.T4),
        ("T4_X_4", Machine.T4_X_4),
        ("g4dn.12xlarge", Machine.T4_X_4),
        ("L4", Machine.L4),
        ("g6.4xlarge", Machine.L4),
        ("L4_X_4", Machine.L4_X_4),
        ("g6.12xlarge", Machine.L4_X_4),
        ("L4_X_8", Machine.L4_X_8),
        ("g6.48xlarge", Machine.L4_X_8),
        ("A10G", Machine.A10G),
        ("g5.8xlarge", Machine.A10G),
        ("A10G_X_4", Machine.A10G_X_4),
        ("g5.12xlarge", Machine.A10G_X_4),
        ("A10G_X_8", Machine.A10G_X_8),
        ("g5.48xlarge", Machine.A10G_X_8),
        ("L40S", Machine.L40S),
        ("g6e.4xlarge", Machine.L40S),
        ("L40S_X_4", Machine.L40S_X_4),
        ("g6e.12xlarge", Machine.L40S_X_4),
        ("L40S_X_8", Machine.L40S_X_8),
        ("g6e.48xlarge", Machine.L40S_X_8),
        ("A100_X_8", Machine.A100_X_8),
        ("p4d.24xlarge", Machine.A100_X_8),
        ("H100_X_8", Machine.H100_X_8),
        ("p5.48xlarge", Machine.H100_X_8),
        ("H200_X_8", Machine.H200_X_8),
        ("p5en.48xlarge", Machine.H200_X_8),
        # instance types not available as predefined enums
        ("some-instance", Machine("some-instance", "some-instance")),
        ("i4i.8xlarge", Machine("i4i.8xlarge", "i4i.8xlarge")),
        ("CPU_SMALL", Machine.CPU_SMALL),
        ("n2d-standard-2", Machine.CPU_SMALL),  # GCP
        ("L4_X_2", Machine.L4_X_2),
        ("g2-standard-24", Machine.L4_X_2),  # GCP
        ("A100_X_2", Machine.A100_X_2),
        ("a2-ultragpu-2g", Machine.A100_X_2),  # GCP
        ("A100_X_4", Machine.A100_X_4),
        ("a2-ultragpu-4g", Machine.A100_X_4),  # GCP
        ("B200_X_8", Machine.B200_X_8),
        ("a4-highgpu-8g", Machine.B200_X_8),  # GCP
    ],
)
def test_machine_from_str(machine_str: str, expected_cls_value: Machine):
    assert Machine.from_str(machine_str) == expected_cls_value

    assert Machine.from_str("unknown", machine_str) == expected_cls_value
