from typing import TYPE_CHECKING, List, Optional, Union

from lightning_sdk.api import TeamspaceApi
from lightning_sdk.organization import Organization
from lightning_sdk.owner import Owner
from lightning_sdk.user import User
from lightning_sdk.utils import _get_organizations_for_authed_user, _resolve_org, _resolve_teamspace_name, _resolve_user

if TYPE_CHECKING:
    from lightning_sdk.studio import Studio


class Teamspace:
    """A teamspace is a collection of Studios, Clusters, Members and an associated Budget.

    Args:
        name: the name of the teamspace
        org: the owning organization
        user: the owning user

    Note:
        Either user or organization should be specified.

    Note:
        Arguments will be automatically inferred from environment variables if possible,
        unless explicitly specified

    """

    def __init__(
        self,
        name: Optional[str] = None,
        org: Optional[Union[str, Organization]] = None,
        user: Optional[Union[str, User]] = None,
    ) -> None:
        self._teamspace_api = TeamspaceApi()

        name = _resolve_teamspace_name(name)

        if name is None:
            raise ValueError("Teamspace name wasn't provided and could not be inferred from environment")

        if user is not None and org is not None:
            raise ValueError("User and org are mutually exclusive. Please only specify the one who owns the teamspace.")

        if user is not None:
            self._user = _resolve_user(user)
            # don't parse org if user was explicitly provided
            self._org = None
        else:
            self._user = _resolve_user(user)
            self._org = _resolve_org(org)

        self._owner: Owner
        if self._user is None and self._org is None:
            raise RuntimeError(
                "Neither user or org are specified, but one of them has to be the owner of the Teamspace"
            )
        elif self._org is not None:
            self._owner = self._org

        else:
            self._owner = self._user

        try:
            self._teamspace = self._teamspace_api.get_teamspace(name=name, owner_id=self.owner.id)
        except ValueError as e:
            raise _resolve_valueerror_message(e, self.owner, name) from e

    @property
    def name(self) -> str:
        """The teamspace's name."""
        return self._teamspace.name

    @property
    def id(self) -> str:
        """The teamspace's ID."""
        return self._teamspace.id

    @property
    def owner(self) -> Owner:
        """The teamspace's owner."""
        return self._owner

    @property
    def studios(self) -> List["Studio"]:
        """All studios within that teamspace."""
        from lightning_sdk.studio import Studio

        studios = []
        clusters = self._teamspace_api.list_clusters(teamspace_id=self.id)
        for cl in clusters:
            _studios = self._teamspace_api.list_studios(teamspace_id=self.id, cluster_id=cl.cluster_id)
            for s in _studios:
                studios.append(Studio(name=s.name, teamspace=self, cluster=cl.cluster_name, create_ok=False))

        return studios

    @property
    def clusters(self) -> List[str]:
        """All clusters associated with that teamspace."""
        clusters = self._teamspace_api.list_clusters(teamspace_id=self.id)
        return [cl.cluster_name for cl in clusters]

    def __eq__(self, other: "Teamspace") -> bool:
        """Checks whether the provided other object is equal to this one."""
        return (
            type(self) is type(other) and self.name == other.name and self.id == other.id and self.owner == other.owner
        )

    def __repr__(self) -> str:
        """Returns reader friendly representation."""
        return f"Teamspace(name={self.name}, owner={self.owner!r})"

    def __str__(self) -> str:
        """Returns reader friendly representation."""
        return repr(self)


def _resolve_valueerror_message(error: ValueError, owner: Owner, teamspace_name: str) -> ValueError:
    """Resolves the ValueError Message and replaces it with a nicer message."""
    message = error.args[0]
    if message.startswith("Teamspace") and message.endswith("does not exist"):
        entire_ts_name = f"{owner.name}/{teamspace_name}"

        if isinstance(owner, User):
            organizations = _get_organizations_for_authed_user()
            message = (
                f"Teamspace {entire_ts_name} does not exist. "
                "Is it maybe an organizational Teamspace? You are a member of the following organizations: "
                f"{[o.name for o in organizations]}. Maybe specify one of these instead "
                "of your user if the Teamspace belongs to the organization."
            )
        else:
            # organization teamspace owner
            user = User()
            message = (
                f"Teamspace {entire_ts_name} does not exist. "
                f"Is it maybe a user Teamspace. You specified org={owner.name}, "
                "but maybe the Teamspace is part of your user? "
                f"Consider specifying user={user.name} instead of your org."
            )

    return ValueError(message, *error.args[1:])
