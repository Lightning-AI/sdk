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
