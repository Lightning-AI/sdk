import logging
import os
import warnings
from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator, List, Optional, Tuple, Union

from lightning_sdk.api import TeamspaceApi, UserApi
from lightning_sdk.api.utils import _get_cloud_url
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.machine import CloudProvider, Machine

if TYPE_CHECKING:
    from lightning_sdk.organization import Organization
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User


_LIGHTNING_SERVICE_EXECUTION_ID_KEY = "LIGHTNING_SERVICE_EXECUTION_ID"


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


def _resolve_deprecated_provider(
    cloud_provider: Optional[Union[CloudProvider, str]], provider: Optional[Union[CloudProvider, str]]
) -> Optional[Union[CloudProvider, str]]:
    if provider is not None:
        if cloud_provider is not None:
            raise ValueError(
                "Cannot use both 'provider' and 'cloud_provider' at the same time."
                "Please don't set the 'provider' as it will be deprecated!"
            )

        warnings.warn(
            "The 'provider' argument will be deprecated in the future! "
            "Please consider using the 'cloud_provider' argument instead!",
            DeprecationWarning,
        )
        return provider

    if cloud_provider is None:
        from lightning_sdk.utils.config import Config, DefaultConfigKeys

        config = Config()
        cloud_provider = config.get_value(DefaultConfigKeys.cloud_provider)

    return cloud_provider


def _resolve_deprecated_cluster(cloud_account: Optional[str], cluster: Optional[str]) -> Optional[str]:
    if cluster is not None:
        if cloud_account is not None:
            raise ValueError(
                "Cannot use both 'cluster' and 'cloud_account' at the same time."
                "Please don't set the 'cluster' as it will be deprecated!"
            )

        warnings.warn(
            "The 'cluster' argument will be deprecated in the future! "
            "Please consider using the 'cloud_account' argument instead!",
            DeprecationWarning,
        )
        return cluster

    if cloud_account is None:
        from lightning_sdk.utils.config import Config, DefaultConfigKeys

        config = Config()
        cloud_account = config.get_value(DefaultConfigKeys.cloud_account)

    return cloud_account


def _resolve_org_name(name: Optional[str]) -> Optional[str]:
    if name is None:
        name = os.environ.get("LIGHTNING_ORG", "") or None
    if name is None:
        from lightning_sdk.utils.config import Config, DefaultConfigKeys

        config = Config()
        name = config.get_value(DefaultConfigKeys.organization)
    return name


def _resolve_org(org: Optional[Union[str, "Organization"]]) -> Optional["Organization"]:
    from lightning_sdk.organization import Organization

    if isinstance(org, Organization):
        return org

    org = _resolve_org_name(org)

    if org is None:
        return None

    from lightning_sdk.organization import Organization

    try:
        return Organization(name=org)
    # Handle case where user name is mistakenly used as organization name
    except ApiException as ae:
        if ae.status == 404:
            raise ValueError(f"Organization '{org}' does not exist or you are not a member of it.") from ae
        raise RuntimeError(f"Failed to resolve organization '{org}': {ae}") from ae


def _resolve_user_name(name: Optional[str]) -> Optional[str]:
    if name is None:
        name = os.environ.get("LIGHTNING_USERNAME", "") or None
    if name is None:
        from lightning_sdk.utils.config import Config, DefaultConfigKeys

        config = Config()
        name = config.get_value(DefaultConfigKeys.user)
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
    if name is None:
        from lightning_sdk.utils.config import Config, DefaultConfigKeys

        config = Config()
        name = config.get_value(DefaultConfigKeys.teamspace_name)
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

    # if user was specified explicitly, use that, else resolve
    if user is not None:
        user = _resolve_user(user=user)
        return Teamspace(name=teamspace, user=user)

    org = _resolve_org(org)

    if org is not None:
        return Teamspace(name=teamspace, org=org)

    user = _resolve_user(user)

    # If still no user or org resolved, try config defaults
    if user is None and org is None:
        from lightning_sdk.utils.config import Config, DefaultConfigKeys

        config = Config()
        owner_type = config.get_value(DefaultConfigKeys.teamspace_owner_type)
        owner_name = config.get_value(DefaultConfigKeys.teamspace_owner)

        if owner_type and owner_name:
            if owner_type.lower() == "organization":
                org = _resolve_org(owner_name)
            elif owner_type.lower() == "user":
                user = _resolve_user(owner_name)

    # Final resolution check
    if org is not None:
        return Teamspace(name=teamspace, org=org)

    if user is not None:
        return Teamspace(name=teamspace, user=user)

    raise RuntimeError("Neither user nor org provided, but one of them needs to be provided")


def _get_organizations_for_authed_user() -> List["Organization"]:
    """Returns Organizations the current Authed user is a member of."""
    from lightning_sdk.organization import Organization

    _orgs = UserApi()._get_organizations_for_authed_user()
    return [Organization(_org.name) for _org in _orgs]


def _get_teamspace_names_for_authed_user() -> List[str]:
    """Returns Teamspace's names the current Authed user is a member of."""
    teamspaces = UserApi()._get_all_teamspace_memberships("")
    return sorted([ts.name for ts in teamspaces])


def _get_authed_user() -> "User":
    from lightning_sdk.user import User

    user_id = TeamspaceApi()._get_authed_user_id()
    _user = UserApi()._get_user_by_id(user_id)
    return User(name=_user.username)


@contextmanager
def skip_studio_init() -> Generator[None, None, None]:
    """Skip studio init based on current runtime."""
    from lightning_sdk.studio import Studio

    prev_studio_init_state = getattr(Studio._skip_init, "value", False)
    Studio._skip_init.value = True

    yield

    Studio._skip_init.value = prev_studio_init_state


@contextmanager
def skip_studio_setup() -> Generator[None, None, None]:
    """Skip studio setup based on current runtime."""
    from lightning_sdk.studio import Studio

    prev_studio_setup_state = getattr(Studio._skip_setup, "value", False)
    Studio._skip_setup.value = True

    yield

    Studio._skip_setup.value = prev_studio_setup_state


@contextmanager
def prevent_refetch_studio(studio: "Studio") -> Generator[None, None, None]:
    """Prevent refetching the studio based on current runtime."""
    prev_prevent_refetch_state = getattr(studio, "_prevent_refetch", False)
    studio._prevent_refetch = True

    yield

    studio._prevent_refetch = prev_prevent_refetch_state


def _parse_model_and_version(name: str) -> Tuple[str, Optional[str]]:
    """Parse the model name and version from the given string.

    >>> _parse_model_and_version("org/teamspace/modelname")
    ('org/teamspace/modelname', None)
    >>> _parse_model_and_version("org/teamspace/modelname:version")
    ('org/teamspace/modelname', 'version')
    """
    parts = name.split(":")
    if len(parts) == 1:
        return parts[0], None
    if len(parts) == 2:
        return parts[0], parts[1]
    # The rest of the validation for name and version happens in the backend
    raise ValueError(
        "Model version is expected to be in the format `entity/modelname:version` separated by a single colon,"
        f" but got: {name}"
    )


def in_studio() -> bool:
    """Returns true if inside a studio, else false."""
    has_cloudspace_id = bool(os.getenv("LIGHTNING_CLOUD_SPACE_ID", None))
    is_interactive = os.getenv("LIGHTNING_INTERACTIVE", "false") == "true"
    return has_cloudspace_id and is_interactive


def _get_studio_url(studio: "Studio", turn_on: bool = False) -> str:
    cloud_url = _get_cloud_url().replace(":443", "")
    base_url = f"{cloud_url}/{studio.owner.name}/{studio.teamspace.name}/studios/{studio.name}/code"

    if turn_on:
        return f"{base_url}?turnOn=true"
    return base_url


def _get_org_id(teamspace: "Teamspace") -> str:
    from lightning_sdk.organization import Organization

    if isinstance(teamspace.owner, Organization):
        return teamspace.owner.id
    return ""
