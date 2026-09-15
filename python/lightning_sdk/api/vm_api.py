"""Internal API client for VM (cloud instance) requests."""

import time
from typing import Callable, List, Optional

from lightning_sdk.lightning_cloud.openapi import (
    V1ClusterState,
    V1CreateInstanceRequest,
    V1ExternalCluster,
    V1Instance,
)
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.lightning_cloud.rest_client import LightningClient

TERMINAL_STATUSES = frozenset({"failed", "reclaimed", "deleting"})


class VMFailedError(RuntimeError):
    """Raised when a VM reaches a terminal failure status while waiting."""


class VMNotFoundError(RuntimeError):
    """Raised when a VM disappears while waiting."""


class VMApi:
    """Internal API client for VM requests (mainly http requests)."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)

    def create_vm(
        self,
        name: str,
        org_id: str,
        teamspace_id: str,
        cluster_id: str,
        instance_type: str,
        volume_size: Optional[int] = None,
        spot: bool = False,
    ) -> V1Instance:
        """Create a VM (cloud instance)."""
        body = V1CreateInstanceRequest(
            name=name,
            organization_id=org_id,
            project_id=teamspace_id,
            cluster_id=cluster_id,
            instance_type=instance_type,
            spot=spot,
        )
        if volume_size is not None:
            body.volume_size = str(volume_size)
        return self._client.cloud_instances_service_create_instance(body=body)

    def get_vm(self, vm_id: str, org_id: str) -> Optional[V1Instance]:
        """Get a VM by id, returning None if it does not exist."""
        try:
            return self._client.cloud_instances_service_get_instance(id=vm_id, organization_id=org_id)
        except ApiException as ex:
            if "Reason: Not Found" in str(ex):
                return None
            raise ex

    def get_vm_by_name(self, name: str, teamspace_id: str) -> Optional[V1Instance]:
        """Get a VM by name within a teamspace, returning None if not found."""
        matches = [vm for vm in self.list_vms(teamspace_id) if vm.name == name]
        if len(matches) > 1:
            raise ValueError(f"Multiple VMs named {name!r}; use the VM id instead.")
        return matches[0] if matches else None

    def list_vms(self, teamspace_id: str) -> List[V1Instance]:
        """List all VMs in a teamspace, paginating through all pages."""
        vms: List[V1Instance] = []
        page_token = None
        while True:
            kwargs = {"project_id": teamspace_id, "limit": "100"}
            if page_token:
                kwargs["page_token"] = page_token
            response = self._client.cloud_instances_service_list_instances(**kwargs)
            vms.extend(response.instances or [])
            page_token = response.next_page_token
            if not page_token:
                break
        return vms

    def list_machine_clusters(self, org_id: str) -> List[V1ExternalCluster]:
        """List the organization's running machine clusters."""
        response = self._client.cluster_service_list_clusters(org_id=org_id)
        return [
            cluster
            for cluster in (response.clusters or [])
            if cluster.spec.machine_v1 is not None and cluster.status.phase == V1ClusterState.RUNNING
        ]

    def delete_vm(self, vm_id: str, org_id: str) -> None:
        """Delete a VM by id."""
        self._client.cloud_instances_service_delete_instance(id=vm_id, organization_id=org_id)

    def wait_for_status(
        self,
        vm_id: str,
        org_id: str,
        target: str = "running",
        timeout: float = 600.0,
        poll_interval: float = 5.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> V1Instance:
        """Poll a VM until it reaches the target status, fails, disappears, or times out."""
        deadline = clock() + timeout
        while True:
            vm = self.get_vm(vm_id, org_id)
            if vm is None:
                raise VMNotFoundError(f"VM {vm_id} no longer exists.")
            if vm.status == target:
                return vm
            if vm.status in TERMINAL_STATUSES:
                reason = f": {vm.status_reason}" if vm.status_reason else ""
                raise VMFailedError(f"VM {vm_id} entered status {vm.status!r}{reason}")
            if clock() >= deadline:
                raise TimeoutError(
                    f"VM {vm_id} did not reach status {target!r} within {timeout:.0f}s (last: {vm.status!r})"
                )
            sleep(poll_interval)
