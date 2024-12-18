from typing import Literal

import pytest

from lightning_sdk.utils.dynamic import ConditionBaseMeta


@pytest.mark.parametrize(
    ("condition_result", "expected_method_name", "nonexpected_method_name"),
    [
        (True, "method_a", "method_b"),
        (False, "method_b", "method_a"),
    ],
)
def test_condition_base_meta(
    condition_result: bool,
    expected_method_name: Literal["method_a", "method_b"],
    nonexpected_method_name: Literal["method_a", "method_b"],
):
    class A:
        def method_a(self):
            return "method_a"

    class B:
        def method_b(self):
            return "method_b"

    class MyNewClass(metaclass=ConditionBaseMeta, condition_func=lambda: condition_result, base_true=A, base_false=B):
        pass

    myclass = MyNewClass()

    assert issubclass(MyNewClass, A) == condition_result
    assert issubclass(MyNewClass, B) != condition_result

    assert isinstance(myclass, A) == condition_result
    assert isinstance(myclass, B) != condition_result

    assert hasattr(myclass, expected_method_name)
    assert not hasattr(myclass, nonexpected_method_name)

    assert getattr(myclass, expected_method_name)() == expected_method_name

    with pytest.raises(AttributeError):
        getattr(myclass, nonexpected_method_name)()
