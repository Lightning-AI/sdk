from lightning_sdk.utils import DeprecationEnum
import pytest


def test_deprecation_enum():
    class MyEnum(DeprecationEnum):
        A = 1
        B = 2
        C = 2, "B"

    assert MyEnum.A == 1
    assert MyEnum.B == 2
    with pytest.warns(DeprecationWarning, matches="MyEnum.C is deprecated. Use MyEnum.B instead."):
        assert MyEnum.C == 2
