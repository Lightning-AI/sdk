"""Teamspace-scoped private networking for native VMs."""

from typing import Dict, List, Optional, Sequence, Union

from lightning_sdk.api.vm_network_group_api import VMNetworkGroupApi
from lightning_sdk.lightning_cloud.openapi import V1VMNetworkGroup
from lightning_sdk.organization import Organization
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User
from lightning_sdk.utils.logging import TrackCallsMeta
from lightning_sdk.vm import VM, _default_machine_cluster, _require_org_id, _resolve


class VMNetworkGroup(metaclass=TrackCallsMeta):
    """A private network for native VMs in one teamspace and machine cluster.

    Creation and additions require the per-user ``VMNetworkGroups`` feature flag.
    Removal and deletion remain available when the flag is disabled.
    """

    def __init__(
        self,
        group_id: str,
        teamspace: Optional[Union[str, Teamspace]] = None,
        org: Optional[Union[str, Organization]] = None,
        user: Optional[Union[str, User]] = None,
    ) -> None:
        self._teamspace = _resolve(teamspace, org, user)
        self._org_id = _require_org_id(self._teamspace)
        self._api = VMNetworkGroupApi()
        group = self._api.get(group_id, self._org_id)
        if group is None:
            raise ValueError(f"VM network group '{group_id}' was not found.")
        self._check_scope(group)
        self._group = group

    @classmethod
    def _from_group(
        cls, group: V1VMNetworkGroup, teamspace: Teamspace, org_id: str, api: VMNetworkGroupApi
    ) -> "VMNetworkGroup":
        result = cls.__new__(cls)
        result._teamspace, result._org_id, result._api, result._group = teamspace, org_id, api, group
        result._check_scope(group)
        return result

    @classmethod
    def create(
        cls,
        name: str,
        teamspace: Optional[Union[str, Teamspace]] = None,
        org: Optional[Union[str, Organization]] = None,
        user: Optional[Union[str, User]] = None,
        cloud_account: Optional[str] = None,
    ) -> "VMNetworkGroup":
        """Create an empty group; ``cloud_account`` is a machine-cluster ID."""
        resolved = _resolve(teamspace, org, user)
        org_id = _require_org_id(resolved)
        api = VMNetworkGroupApi()
        group = api.create(name, org_id, resolved.id, cloud_account or _default_machine_cluster(org_id))
        return cls._from_group(group, resolved, org_id, api)

    @staticmethod
    def list(
        teamspace: Optional[Union[str, Teamspace]] = None,
        org: Optional[Union[str, Organization]] = None,
        user: Optional[Union[str, User]] = None,
    ) -> List["VMNetworkGroup"]:
        """List the groups in a teamspace."""
        resolved = _resolve(teamspace, org, user)
        org_id, api = _require_org_id(resolved), VMNetworkGroupApi()
        return [VMNetworkGroup._from_group(group, resolved, org_id, api) for group in api.list(org_id, resolved.id)]

    def _check_scope(self, group: V1VMNetworkGroup) -> None:
        if group.organization_id != self._org_id or group.project_id != self._teamspace.id:
            raise ValueError("VM network group does not belong to the selected teamspace.")

    def _instance_ids(self, members: Sequence[Union[VM, str]]) -> List[str]:
        result = []
        for member in members:
            if isinstance(member, VM):
                if member.teamspace.id != self._teamspace.id:
                    raise ValueError("All member VMs must belong to the network group's teamspace.")
                instance_id = member.id
            elif isinstance(member, str):
                instance_id = member
            else:
                raise TypeError("Members must be VM objects or VM IDs.")
            if not instance_id:
                raise ValueError("VM IDs must not be empty.")
            if instance_id in result:
                raise ValueError("Duplicate VM in network-group membership.")
            result.append(instance_id)
        return result

    def refresh(self) -> "VMNetworkGroup":
        """Reload membership, addresses, and status."""
        group = self._api.get(self.id, self._org_id)
        if group is None:
            raise ValueError(f"VM network group '{self.id}' no longer exists.")
        self._check_scope(group)
        self._group = group
        return self

    def set_members(
        self, members: Sequence[Union[VM, str]], wait: bool = False, timeout: float = 600
    ) -> "VMNetworkGroup":
        """Replace membership using this object's revision; stale revisions raise a conflict."""
        group = self._api.set_members(self.id, self._org_id, self.revision, self._instance_ids(members))
        self._check_scope(group)
        self._group = group
        return self.wait(timeout=timeout) if wait else self

    def attach(self, *members: Union[VM, str], wait: bool = False, timeout: float = 600) -> "VMNetworkGroup":
        """Add VMs without removing members from this object's current snapshot."""
        ids = self._instance_ids(members)
        return self.set_members(list(dict.fromkeys([*self.member_ids, *ids])), wait=wait, timeout=timeout)

    def detach(self, *members: Union[VM, str], wait: bool = False, timeout: float = 600) -> "VMNetworkGroup":
        """Remove VMs; ``wait=True`` waits for all affected hosts to acknowledge revocation."""
        ids = set(self._instance_ids(members))
        return self.set_members([member for member in self.member_ids if member not in ids], wait=wait, timeout=timeout)

    def wait(self, timeout: float = 600) -> "VMNetworkGroup":
        """Wait for this membership revision and its private addresses to be ready."""
        group = self._api.wait(self.id, self._org_id, self.revision, timeout=timeout)
        if group is None:
            raise ValueError(f"VM network group '{self.id}' no longer exists.")
        self._check_scope(group)
        self._group = group
        return self

    def delete(self, wait: bool = False, timeout: float = 600) -> None:
        """Delete the group; optionally wait until all address holds are released."""
        self._api.delete(self.id, self._org_id)
        if wait:
            self._api.wait(self.id, self._org_id, self.revision, timeout=timeout, deleted=True)

    @property
    def id(self) -> str:
        return self._group.id

    @property
    def name(self) -> str:
        return self._group.name

    @property
    def status(self) -> str:
        return self._group.status

    @property
    def error(self) -> str:
        return self._group.error or ""

    @property
    def revision(self) -> int:
        return int(self._group.revision)

    @property
    def member_ids(self) -> List[str]:
        return [member.instance_id for member in self._group.members or []]

    @property
    def private_addresses(self) -> Dict[str, str]:
        """Return known advertised node addresses keyed by VM ID; call ``wait`` before joining nodes."""
        return {
            member.instance_id: member.private_address for member in self._group.members or [] if member.private_address
        }
