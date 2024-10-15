import pytest

from lightning_sdk.utils.enum import DeprecationEnum


def test_deprecation_enum():
    class MyEnum(DeprecationEnum):
        A = 1
        B = 2
        C = 3, "B"

    assert MyEnum.A.value == 1
    assert MyEnum.B.value == 2
    with pytest.warns(DeprecationWarning, match="MyEnum.C is deprecated. Use MyEnum.B instead!"):
        # the value is defined as 3 to be unique, but the preferred value is B which is, why value.C
        # is rerouted to value.B after triggering a deprecation warning
        # this prevents from having to check multiple values for the same enum in logic outside the enum
        # so that all cases using the enum just need to care about the new value
        assert MyEnum.C.value == 2
