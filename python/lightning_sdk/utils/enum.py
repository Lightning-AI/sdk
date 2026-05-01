from enum import Enum, EnumMeta, unique
from types import MappingProxyType
from typing import Any, Dict, Iterator, Union


# We silence annotation errors as the function signatures are exactly the same in python core enum.py
# modified from https://stackoverflow.com/a/62309159
class OnAccess(EnumMeta):
    """Runs a user-specified function whenever member is accessed."""

    def __getattribute__(cls, name: str) -> Any:  # noqa: N805
        """Called when an attribute is accessed."""
        obj = super().__getattribute__(name)
        if isinstance(obj, Enum) and obj._on_access:
            obj._on_access()
        return _resolve_deprecated_enum_fields(obj)

    def __getitem__(cls, name: str) -> Any:  # noqa: N805
        """Called when an item is accessed."""
        member = super().__getitem__(name)
        if isinstance(member, Enum) and member._on_access:
            member._on_access()

        return _resolve_deprecated_enum_fields(member)

    def __call__(
        cls,  # noqa: N805
        value,  # noqa: ANN001
        names=None,  # noqa: ANN001
        *,
        module=None,  # noqa: ANN001
        qualname=None,  # noqa: ANN001
        type=None,  # noqa: A002, ANN001
        start=1,  # noqa: ANN001
    ) -> Any:
        obj = super().__call__(value, names, module=module, qualname=qualname, type=type, start=start)
        if isinstance(obj, Enum) and obj._on_access:
            obj._on_access()
        return _resolve_deprecated_enum_fields(obj)

    @staticmethod
    def _filter_func(member: "DeprecationEnum") -> bool:
        return not member.deprecated

    def __iter__(cls) -> Iterator["DeprecationEnum"]:  # noqa: N805
        """Returns members in definition order.

        Excludes deprecated members

        """
        return filter(cls._filter_func, (cls._member_map_[name] for name in cls._member_names_))

    def __len__(cls) -> int:  # noqa: N805
        """Length of the enum excluding deprecated members."""
        return len(cls.__members__)

    @property
    def __members__(cls) -> Dict[str, "DeprecationEnum"]:  # noqa: N805
        """Returns a mapping of member name->value.

        This mapping lists all enum members, including aliases. Note that this is a read-only view of the internal
        mapping.

        Excludes deprecated members.

        """
        return MappingProxyType(
            {name: member for name, member in cls._member_map_.items() if not cls._filter_func(member)}
        )

    def __reversed__(cls) -> Iterator["DeprecationEnum"]:  # noqa: N805
        """Returns members in reverse definition order.

        Excludes deprecated members

        """
        return filter(cls._filter_func, (cls._member_map_[name] for name in reversed(cls._member_names_)))


def _resolve_deprecated_enum_fields(value: Union[Any, "DeprecationEnum"]) -> Union[Any, "DeprecationEnum"]:
    """Resolves deprecated enum fields to their preferred values."""
    if getattr(value, "deprecated", False):
        return value.__class__[value.preferred_way]
    return value


# NOTE: even deprecated enums need to have unique values.
# otherwise the deprecation warning will not be triggered
# as duplicated values are handled as aliases towards the original value
# and the original value is not accessed. However, _resolve_deprecated_enum_fields
# will handle this case and return the preferred value
@unique
class DeprecationEnum(Enum, metaclass=OnAccess):
    def __new__(cls, value, *args) -> Any:  # noqa: ANN001, ANN002
        member = object.__new__(cls)
        member._value_ = value
        member.deprecated = False
        member._on_access = None

        if args:
            member.preferred_way = args[0]
            member._on_access = member.deprecate
            member.deprecated = True

        return member

    def deprecate(self) -> None:
        import warnings

        clsname = self.__class__.__name__

        warnings.warn(
            f"{clsname}.{self.name} is deprecated. Use {clsname}.{self.preferred_way} instead!",
            DeprecationWarning,
            stacklevel=3,
        )
