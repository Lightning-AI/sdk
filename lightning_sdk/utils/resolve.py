import logging
import os
import warnings
from contextlib import contextmanager
from functools import lru_cache
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
    """Create and configure a logger with a stream handler.

    Args:
        name: The logger name (typically ``__name__`` of the calling module).
        level: Logging level (default ``INFO``).

    Returns:
        logging.Logger: A configured logger instance.
    """
    _logger = logging.getLogger(name)
    _handler = logging.StreamHandler()
    _handler.setLevel(level)
    _logger.setLevel(level)
    _formatter = logging.Formatter("%(levelname)s - %(message)s")
    _handler.setFormatter(_formatter)
    _logger.addHandler(_handler)
    return _logger


def _resolve_deprecated_cloud_compute(machine: Machine, cloud_compute: Optional[Machine]) -> Machine:
    """Resolve the active machine, handling the deprecated ``cloud_compute`` argument.

    Args:
        machine: The ``machine`` argument passed by the caller.
        cloud_compute: The deprecated ``cloud_compute`` argument (use ``machine`` instead).

    Returns:
        Machine: The resolved machine to use.

    Raises:
        ValueError: If both ``machine`` and ``cloud_compute`` are explicitly set.
    """
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
    """Resolve the active cloud provider, handling the deprecated ``provider`` argument.

    Falls back to the configured default from :class:`~lightning_sdk.utils.config.Config`
    when neither argument is set.

    Args:
        cloud_provider: The ``cloud_provider`` argument passed by the caller.
        provider: The deprecated ``provider`` argument (use ``cloud_provider`` instead).

    Returns:
        Optional[Union[CloudProvider, str]]: The resolved cloud provider, or ``None``.

    Raises:
        ValueError: If both ``cloud_provider`` and ``provider`` are explicitly set.
    """
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


def _resolve_deprecated_cluster(
    cloud_account: Optional[str], cluster: Optional[str], current_cloud_account: Optional[str] = None
) -> Optional[str]:
    """Resolve the active cloud account, handling the deprecated ``cluster`` argument.

    Falls back to the configured default from :class:`~lightning_sdk.utils.config.Config`
    and then ``current_cloud_account`` when neither argument is set.

    Args:
        cloud_account: The ``cloud_account`` argument passed by the caller.
        cluster: The deprecated ``cluster`` argument (use ``cloud_account`` instead).
        current_cloud_account: Optional fallback account ID when nothing else resolves.

    Returns:
        Optional[str]: The resolved cloud account ID, or ``None``.

    Raises:
        ValueError: If both ``cloud_account`` and ``cluster`` are explicitly set.
    """
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

        if cloud_account is None:
            cloud_account = current_cloud_account

    return cloud_account


def _resolve_org_name(name: Optional[str]) -> Optional[str]:
    """Return the organisation name, falling back to the env var and config when ``None``.

    Args:
        name: Explicit organisation name, or ``None`` to auto-resolve.

    Returns:
        Optional[str]: Resolved organisation name, or ``None`` if not determinable.
    """
    if name is None:
        name = os.environ.get("LIGHTNING_ORG", "") or None
    if name is None:
        from lightning_sdk.utils.config import Config, DefaultConfigKeys

        config = Config()
        name = config.get_value(DefaultConfigKeys.organization)
    return name


def _resolve_org(org: Optional[Union[str, "Organization"]]) -> Optional["Organization"]:
    """Resolve an Organisation instance from a name string or return it unchanged.

    Args:
        org: An ``Organization`` instance, a name string, or ``None``.

    Returns:
        Optional[Organization]: The resolved organisation, or ``None``.

    Raises:
        ValueError: If the organisation name cannot be found.
    """
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
    """Return the username, falling back to the env var and config when ``None``.

    Args:
        name: Explicit username, or ``None`` to auto-resolve.

    Returns:
        Optional[str]: Resolved username, or ``None`` if not determinable.
    """
    if name is None:
        name = os.environ.get("LIGHTNING_USERNAME", "") or None
    if name is None:
        from lightning_sdk.utils.config import Config, DefaultConfigKeys

        config = Config()
        name = config.get_value(DefaultConfigKeys.user)
    return name


def _resolve_user(user: Optional[Union[str, "User"]]) -> Optional["User"]:
    """Resolve a User instance from a name string or return it unchanged.

    Args:
        user: A ``User`` instance, a username string, or ``None``.

    Returns:
        Optional[User]: The resolved user, or ``None``.
    """
    from lightning_sdk.user import User

    if isinstance(user, User):
        return user

    user = _resolve_user_name(user)
    if user is None:
        return None

    return User(name=user)


def _resolve_teamspace_name(name: Optional[str]) -> Optional[str]:
    """Return the teamspace name, falling back to the env var and config when ``None``.

    Args:
        name: Explicit teamspace name, or ``None`` to auto-resolve.

    Returns:
        Optional[str]: Resolved teamspace name, or ``None`` if not determinable.
    """
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
    """Resolve a Teamspace from name/org/user arguments.

    Looks up the teamspace name from env vars and config when not provided, then
    constructs a Teamspace object with the appropriate owner.

    Args:
        teamspace: A ``Teamspace`` instance, a teamspace name string, or ``None``.
        org: The owning organisation (name or instance), or ``None``.
        user: The owning user (name or instance), or ``None``.

    Returns:
        Optional[Teamspace]: The resolved teamspace, or ``None`` if the name cannot be
        determined.

    Raises:
        RuntimeError: If the teamspace name resolves but neither a user nor org can be
            determined.
    """
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


def _get_organizations_for_authed_user(user_api: Optional[UserApi] = None) -> List["Organization"]:
    """Returns Organizations the current Authed user is a member of."""
    from lightning_sdk.organization import Organization

    _orgs = (user_api or UserApi())._get_organizations_for_authed_user()
    return [Organization(_org.name) for _org in _orgs]


def _get_teamspace_names_for_authed_user(user_api: Optional[UserApi] = None) -> List[str]:
    """Returns Teamspace's names the current Authed user is a member of."""
    teamspaces = (user_api or UserApi())._get_all_teamspace_memberships("")
    return sorted([ts.name for ts in teamspaces])


@lru_cache(maxsize=1)
def _get_authed_user(user_api: Optional[UserApi] = None, teamspace_api: Optional[TeamspaceApi] = None) -> "User":
    """Return the currently authenticated user (cached after the first call).

    Args:
        user_api: Optional ``UserApi`` instance; a new one is created when ``None``.
        teamspace_api: Optional ``TeamspaceApi`` instance used to fetch the authed user ID.

    Returns:
        User: The authenticated user.
    """
    from lightning_sdk.user import User

    user_id = (teamspace_api or TeamspaceApi())._get_authed_user_id()
    _user = (user_api or UserApi())._get_user_by_id(user_id)
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
    """Build the Lightning AI web URL for a studio.

    Args:
        studio: The studio to generate a URL for.
        turn_on: When ``True``, appends ``?turnOn=true`` to start the studio.

    Returns:
        str: The fully-qualified URL to the studio's code view.
    """
    cloud_url = _get_cloud_url().replace(":443", "")
    base_url = f"{cloud_url}/{studio.owner.name}/{studio.teamspace.name}/studios/{studio.name}/code"

    if turn_on:
        return f"{base_url}?turnOn=true"
    return base_url


def _get_org_id(teamspace: "Teamspace") -> str:
    """Return the organisation ID for a teamspace, or an empty string for user-owned teamspaces.

    Args:
        teamspace: The teamspace whose owner to inspect.

    Returns:
        str: The organisation ID, or ``""`` if the teamspace is owned by a user.
    """
    from lightning_sdk.organization import Organization

    if isinstance(teamspace.owner, Organization):
        return teamspace.owner.id
    return ""
