from abc import ABCMeta
from typing import Any, Callable, Tuple, Type


class ConditionBaseMeta(ABCMeta):
    """Metaclass that allows for conditional inheritance.

    This metaclass is used to conditionally inherit from two base classes
    based on the result of a given condition function.

    Example usage:
    ```
    def my_condition():
        return some_condition  # Define your condition here

    class A:
        pass

    class B:
        pass

    class MyNewClass(metaclass=ConditionBaseMeta, condition_func=my_condition, base_true=A, base_false=B):
        pass
    ```

    Args:
        cls: The metaclass itself.
        name: The name of the class being created.
        bases: The base classes of the class being created.
        attrs: The attributes of the class being created.
        condition_func: The function that determines which base class to inherit from.
        base_true: The base class to inherit from if the condition function returns True.
        base_false: The base class to inherit from if the condition function returns False.

    Returns:
        type: The new class with the appropriate base class.
    """

    def __new__(
        cls,
        name: str,
        bases: Tuple[type, ...],
        attrs: dict,
        condition_func: Callable[[], bool],
        base_true: Type,
        base_false: Type,
    ) -> Type:
        # Helper function to determine the base class
        def get_base() -> type:
            return base_true if condition_func() else base_false

        base = get_base()
        attrs["_base"] = base

        # Create the final class, inheriting from both the intermediate base and the original bases
        return super().__new__(cls, name, (base, *bases), attrs)

    def __getattr__(cls, name: str) -> Any:
        """Get an attribute from the appropriate base class."""
        # Delegate attribute lookup to the appropriate base class
        return getattr(cls._base, name)
