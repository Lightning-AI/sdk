import logging
import os
import warnings
from typing import TYPE_CHECKING, Optional, Union

from lightning_sdk.machine import Machine

if TYPE_CHECKING:
    from lightning_sdk.organization import Organization
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User


def _setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    _logger = logging.getLogger(name)
    _handler = logging.StreamHandler()
    _handler.setLevel(level)
    _logger.setLevel(level)
    _formatter = logging.Formatter("%(levelname)s - %(message)s")
    _handler.setFormatter(_formatter)
    _logger.addHandler(_handler)
    return _logger


def _resolve_deprecated_cloud_compute(machine: Machine, cloud_compute: Optional[Machine]) -> Machine:
    if cloud_compute is not None:
        if machine == Machine.CPU:
            # user explicitly set cloud_compute and not machine, so use cloud_compute
            warnings.warn(
                "The 'cloud_compute' argument will be deprecated in the future! "
                "Please consider using the 'machine' argument instead!",
                DeprecationWarning,
            )
            return cloud_compute

        raise ValueError(
            "Cannot use both 'cloud_compute' and 'machine' at the same time."
            "Please don't set the 'cloud_compute' as it will be deprecated!"
        )

    return machine


def _resolve_org_name(name: Optional[str]) -> Optional[str]:
    if name is None:
        name = os.environ.get("LIGHTNING_ORG", "") or None
    return name


def _resolve_org(org: Optional[Union[str, "Organization"]]) -> Optional["Organization"]:
    from lightning_sdk.organization import Organization

    if isinstance(org, Organization):
        return org

    org = _resolve_org_name(org)

    if org is None:
        return None

    from lightning_sdk.organization import Organization

    return Organization(name=org)


def _resolve_user_name(name: Optional[str]) -> Optional[str]:
    if name is None:
        name = os.environ.get("LIGHTNING_USERNAME", "") or None

    return name


def _resolve_user(user: Optional[Union[str, "User"]]) -> Optional["User"]:
    from lightning_sdk.user import User

    if isinstance(user, User):
        return user

    user = _resolve_user_name(user)

    if user is None:
        return None

    return User(name=user)


def _resolve_teamspace_name(name: Optional[str]) -> Optional[str]:
    if name is None:
        name = os.environ.get("LIGHTNING_TEAMSPACE", "") or None
    return name


def _resolve_teamspace(
    teamspace: Optional[Union[str, "Teamspace"]],
    org: Optional[Union[str, "Organization"]],
    user: Optional[Union[str, "User"]],
) -> Optional["Teamspace"]:
    from lightning_sdk.teamspace import Teamspace

    if isinstance(teamspace, Teamspace):
        return teamspace

    teamspace = _resolve_teamspace_name(teamspace)
    if teamspace is None:
        return None

    org = _resolve_org(org)

    if org is not None:
        return Teamspace(name=teamspace, org=org)

    user = _resolve_user(user)
    if user is None:
        raise RuntimeError("Neither user nor org provided, but one of them needs to be provided")

    return Teamspace(name=teamspace, user=user)
