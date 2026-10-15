"""Internal client for native VM network groups."""

import time
from typing import Callable, List, Optional, Sequence

from lightning_sdk.lightning_cloud.openapi import (
    CloudInstancesServiceSetVMNetworkGroupMembersBody,
    V1CreateVMNetworkGroupRequest,
    V1VMNetworkGroup,
)
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class VMNetworkGroupConflictError(RuntimeError):
    """Raised when membership changes while an operation is waiting."""


class VMNetworkGroupApi:
    """Requests and bounded waits for the network-group service."""

    def __init__(self) -> None:
        # A lost create response must not create another group on retry.
        self._client = LightningClient(retry=False)

    def create(self, name: str, org_id: str, project_id: str, cluster_id: str) -> V1VMNetworkGroup:
        body = V1CreateVMNetworkGroupRequest(
            name=name, organization_id=org_id, project_id=project_id, cluster_id=cluster_id
        )
        return self._client.cloud_instances_service_create_vm_network_group(body=body)

    def get(self, group_id: str, org_id: str, timeout: Optional[float] = None) -> Optional[V1VMNetworkGroup]:
        try:
            kwargs = {"_request_timeout": timeout} if timeout is not None else {}
            return self._client.cloud_instances_service_get_vm_network_group(
                id=group_id, organization_id=org_id, **kwargs
            )
        except ApiException as exc:
            if exc.status == 404:
                return None
            raise

    def list(self, org_id: str, project_id: str) -> List[V1VMNetworkGroup]:
        response = self._client.cloud_instances_service_list_vm_network_groups(
            organization_id=org_id, project_id=project_id
        )
        return response.network_groups or []

    def set_members(self, group_id: str, org_id: str, revision: int, instance_ids: Sequence[str]) -> V1VMNetworkGroup:
        body = CloudInstancesServiceSetVMNetworkGroupMembersBody(
            organization_id=org_id, expected_revision=str(revision), instance_ids=list(instance_ids)
        )
        try:
            return self._client.cloud_instances_service_set_vm_network_group_members(id=group_id, body=body)
        except ApiException as exc:
            if exc.status == 409:
                raise VMNetworkGroupConflictError("Network group changed; refresh it before retrying.") from exc
            raise

    def delete(self, group_id: str, org_id: str) -> None:
        try:
            self._client.cloud_instances_service_delete_vm_network_group(id=group_id, organization_id=org_id)
        except ApiException as exc:
            if exc.status != 404:
                raise

    def wait(
        self,
        group_id: str,
        org_id: str,
        revision: int,
        timeout: float = 600,
        poll_interval: float = 1,
        deleted: bool = False,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> Optional[V1VMNetworkGroup]:
        if timeout <= 0 or poll_interval <= 0:
            raise ValueError("timeout and poll_interval must be positive")
        deadline = clock() + timeout
        last_error = ""
        while True:
            group = self.get(group_id, org_id, timeout=max(0.001, deadline - clock()))
            if group is None:
                if deleted:
                    return None
                raise ValueError(f"VM network group '{group_id}' no longer exists.")
            if not deleted:
                if int(group.revision) != revision:
                    raise VMNetworkGroupConflictError("Network-group membership changed while waiting; refresh it.")
                if group.status == "ready" and all(member.private_address for member in group.members or []):
                    return group
            last_error = group.error or ""
            remaining = deadline - clock()
            if remaining <= 0:
                action = "deleted" if deleted else "ready"
                raise TimeoutError(f"VM network group '{group_id}' did not become {action}: {last_error}")
            sleep(min(poll_interval, remaining))
