import pytest

from lightning_sdk.api.utils import _MACHINE_TO_COMPUTE_NAME


@pytest.mark.parametrize("machine_type", _MACHINE_TO_COMPUTE_NAME.values())
def test_aws_machine_type_api(machine_type, available_aws_instance_types):
    if machine_type.startswith(("cpu", "data-")):
        pytest.skip(f"'{machine_type}' is specific and omitted from testing")
    assert available_aws_instance_types, "No available AWS instance types found"
    assert (
        machine_type in available_aws_instance_types
    ), f"Machine type '{machine_type}' not found in available AWS instance types"
