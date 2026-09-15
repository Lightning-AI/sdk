"""High-level VM (cloud instance) object."""

import os
from datetime import datetime
from typing import List, Optional, Union

from lightning_sdk.api.utils import _machine_to_compute_name
from lightning_sdk.api.vm_api import VMApi
from lightning_sdk.lightning_cloud.openapi import V1Instance
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.machine import Machine
from lightning_sdk.organization import Organization
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User
from lightning_sdk.utils.logging import TrackCallsMeta
from lightning_sdk.utils.resolve import _resolve_teamspace

_TEAMSPACE_HELP = (
    "Pass a teamspace as 'owner/teamspace', set one of LIGHTNING_TEAMSPACE / LIGHTNING_ORG, "
    "or configure a default with 'lightning config set teamspace'."
)


def _require_org_id(teamspace: Teamspace) -> str:
    owner = teamspace.owner
    if not isinstance(owner, Organization):
        raise ValueError(
            f"VMs require a teamspace owned by an organization; '{teamspace.name}' is owned by a user. "
            "Pick an organization teamspace with --teamspace owner/teamspace."
        )
    return owner.id


def _default_machine_cluster(org_id: str) -> str:
    from_env = os.getenv("LIGHTNING_CLUSTER_ID")
    if from_env:
        return from_env

    clusters = VMApi().list_machine_clusters(org_id)
    if not clusters:
        raise ValueError(
            "No machine cluster is available to this organization; "
            "pass cloud_account=... (or --cloud) with a cluster id."
        )
    if len(clusters) > 1:
        candidates = ", ".join(sorted(cluster.id for cluster in clusters))
        raise ValueError(
            f"This organization has several machine clusters ({candidates}); "
            "pass cloud_account=... (or --cloud) with the one to use."
        )
    return clusters[0].id


def _resolve(
    teamspace: Optional[Union[str, Teamspace]],
    org: Optional[Union[str, Organization]],
    user: Optional[Union[str, User]],
) -> Teamspace:
    resolved = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
    if resolved is None:
        raise ValueError("Could not determine the teamspace for your VM. " + _TEAMSPACE_HELP)
    return resolved


class VM(metaclass=TrackCallsMeta):
    """A virtual machine in a Lightning teamspace.

    Args:
        name_or_id: The VM name or id to load.
        teamspace: The teamspace the VM lives in ('owner/teamspace' or a Teamspace).
        org: The organization owning the teamspace.
        user: The user owning the teamspace (VMs require org-owned teamspaces, kept for API symmetry).
    """

    def __init__(
        self,
        name_or_id: str,
        teamspace: Optional[Union[str, Teamspace]] = None,
        org: Optional[Union[str, Organization]] = None,
        user: Optional[Union[str, User]] = None,
    ) -> None:
        self._teamspace = _resolve(teamspace, org, user)
        self._org_id = _require_org_id(self._teamspace)
        self._api = VMApi()

        instance = self._api.get_vm_by_name(name_or_id, self._teamspace.id)
        if instance is None:
            try:
                instance = self._api.get_vm(name_or_id, self._org_id)
            except ApiException as ex:
                raise ValueError(f"Failed to look up VM '{name_or_id}': {ex.reason or ex}") from ex
        if instance is None:
            raise ValueError(
                f"VM '{name_or_id}' was not found in teamspace "
                f"'{self._teamspace.owner.name}/{self._teamspace.name}'."
            )
        self._instance = instance

    @classmethod
    def _from_instance(cls, instance: V1Instance, teamspace: Teamspace, org_id: str, api: VMApi) -> "VM":
        vm = cls.__new__(cls)
        vm._teamspace = teamspace
        vm._org_id = org_id
        vm._api = api
        vm._instance = instance
        return vm

    @classmethod
    def create(
        cls,
        name: str,
        machine: Union[Machine, str],
        teamspace: Optional[Union[str, Teamspace]] = None,
        org: Optional[Union[str, Organization]] = None,
        user: Optional[Union[str, User]] = None,
        cloud_account: Optional[str] = None,
        volume_size: Optional[int] = None,
        spot: bool = False,
        wait: bool = False,
        timeout: float = 600.0,
    ) -> "VM":
        """Create a VM and return it. With ``wait=True`` block until it is running."""
        resolved = _resolve(teamspace, org, user)
        org_id = _require_org_id(resolved)
        api = VMApi()
        if isinstance(machine, str):
            machine = Machine.from_str(machine)
        cluster_id = cloud_account or _default_machine_cluster(org_id)
        instance = api.create_vm(
            name=name,
            org_id=org_id,
            teamspace_id=resolved.id,
            cluster_id=cluster_id,
            instance_type=_machine_to_compute_name(machine),
            volume_size=volume_size,
            spot=spot,
        )
        vm = cls._from_instance(instance, resolved, org_id, api)
        if wait:
            vm.wait(timeout=timeout)
        return vm

    @staticmethod
    def list(
        teamspace: Optional[Union[str, Teamspace]] = None,
        org: Optional[Union[str, Organization]] = None,
        user: Optional[Union[str, User]] = None,
    ) -> List["VM"]:
        """List the VMs in a teamspace."""
        resolved = _resolve(teamspace, org, user)
        org_id = _require_org_id(resolved)
        api = VMApi()
        return [VM._from_instance(i, resolved, org_id, api) for i in api.list_vms(resolved.id)]

    def refresh(self) -> "VM":
        """Re-fetch the VM from the API."""
        instance = self._api.get_vm(self.id, self._org_id)
        if instance is None:
            raise ValueError(f"VM '{self.name}' no longer exists.")
        self._instance = instance
        return self

    def wait(self, timeout: float = 600.0) -> "VM":
        """Block until the VM is running. Raises on failure or timeout."""
        self._instance = self._api.wait_for_status(self.id, self._org_id, timeout=timeout)
        return self

    def delete(self) -> None:
        """Delete the VM. This discards its disk."""
        self._api.delete_vm(self.id, self._org_id)

    @property
    def id(self) -> str:
        return self._instance.id

    @property
    def name(self) -> str:
        return self._instance.name

    @property
    def status(self) -> Optional[str]:
        return self._instance.status

    @property
    def machine(self) -> Optional[str]:
        return self._instance.instance_type

    @property
    def ssh_command(self) -> Optional[str]:
        return self._instance.ssh_command

    @property
    def ssh_host(self) -> Optional[str]:
        return self._instance.ssh_host

    @property
    def ssh_port(self) -> Optional[int]:
        return self._instance.ssh_port

    @property
    def ssh_user(self) -> Optional[str]:
        return self._instance.ssh_user

    @property
    def created_at(self) -> Optional[datetime]:
        return self._instance.created_at

    @property
    def teamspace(self) -> Teamspace:
        return self._teamspace

    def __repr__(self) -> str:
        """Return a debug representation of the VM."""
        return f"VM(name={self.name!r}, status={self.status!r}, teamspace={self._teamspace.name!r})"
