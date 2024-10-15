from abc import ABCMeta
from typing import Any, Callable, Tuple, Union


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
        base_true: type,
        base_false: type,
    ) -> type:
        # Store the condition function and potential base classes as class attributes
        attrs["_condition_func"] = staticmethod(condition_func)
        attrs["_base_true"] = base_true
        attrs["_base_false"] = base_false

        # Helper function to determine the base class
        def get_base() -> type:
            return base_true if condition_func() else base_false

        # Create a new class that inherits from the determined base
        new_class = super().__new__(cls, name, (get_base(),), attrs)

        # Override __class_getitem__ to handle class method lookups
        def __class_getitem(cls: Union[base_true, base_false], name: str) -> Any:
            return getattr(get_base(), name)

        new_class.__class_getitem__ = classmethod(__class_getitem)

        return new_class

    def __getattr__(cls, name: str) -> Any:
        """Get an attribute from the appropriate base class."""
        # Delegate attribute lookup to the appropriate base class
        base = cls._base_true if cls._condition_func() else cls._base_false
        return getattr(base, name)
