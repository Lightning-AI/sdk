"""Internal API client for cloud instances (plain VMs)."""

import json
from contextlib import contextmanager
from typing import Iterator, List, Optional, Tuple

from lightning_sdk.api.utils import cached_lightning_client
from lightning_sdk.lightning_cloud.openapi import (
    V1CreateInstanceRequest,
    V1Instance,
    V1InstanceImage,
)
from lightning_sdk.lightning_cloud.openapi.rest import ApiException

#: The cluster driver backing plain VMs. Only these cloud accounts can host instances.
_MACHINE_DRIVER = "MACHINE"


def _error_message(exc: ApiException) -> str:
    """Return the server's error message, falling back to the HTTP reason."""
    body = getattr(exc, "body", None)
    if isinstance(body, (bytes, bytearray)):
        body = body.decode(errors="replace")
    if body:
        try:
            return str(json.loads(body).get("message") or body)
        except (ValueError, AttributeError):
            return str(body)
    return str(exc.reason or exc)


@contextmanager
def _instance_api_errors() -> Iterator[None]:
    """Turn instance API failures into readable errors instead of swagger tracebacks."""
    try:
        yield
    except ApiException as e:
        message = _error_message(e)
        if e.status == 501:
            raise RuntimeError(f"Not supported by Lightning yet: {message}") from e
        if e.status in (401, 403):
            raise PermissionError(f"Not allowed to manage instances: {message}") from e
        if e.status == 404:
            raise ValueError(message) from e
        raise RuntimeError(f"Lightning API error {e.status}: {message}") from e


class InstanceApi:
    """Internal API client for cloud instance requests (mainly http requests)."""

    def __init__(self) -> None:
        # instance calls are a thin proxy onto the cloud provider: surface their errors
        # (including 501s for not-yet-supported fields) instead of retrying them away.
        self._client = cached_lightning_client(retry=False)

    def create_instance(
        self,
        name: str,
        organization_id: str,
        cloud_account: str,
        instance_type: str,
        volume_size: Optional[int] = None,
        spot: bool = False,
        ports: Optional[List[int]] = None,
        image: Optional[str] = None,
        cloud_init: Optional[str] = None,
    ) -> V1Instance:
        """Create a cloud instance.

        Args:
            name: The name of the instance.
            organization_id: The ID of the organization owning the instance.
            cloud_account: The cloud account (cluster) to create the instance on.
            instance_type: The machine type to provision, e.g. ``cpu-4``.
            volume_size: The root volume size in GB. Defaults to the cloud account's minimum.
            spot: Whether to request an interruptible (spot) instance.
            ports: Ports to expose on the instance's public address.
            image: A curated image name from :meth:`list_instance_images`.
            cloud_init: Raw ``#cloud-config`` YAML applied at boot.

        Returns:
            V1Instance: The newly created instance.
        """
        body = V1CreateInstanceRequest(
            name=name,
            organization_id=organization_id,
            cluster_id=cloud_account,
            instance_type=instance_type,
            spot=spot,
        )
        if volume_size is not None:
            # int64 fields are strings on the wire.
            body.volume_size = str(volume_size)
        if ports:
            body.ports = [str(port) for port in ports]
        if image:
            body.image = image
        if cloud_init:
            body.cloud_init = cloud_init

        with _instance_api_errors():
            return self._client.cloud_instances_service_create_instance(body=body)

    def get_instance(self, instance_id: str, organization_id: str) -> V1Instance:
        """Fetch a single instance by ID.

        Args:
            instance_id: The ID of the instance.
            organization_id: The ID of the organization owning the instance.

        Returns:
            V1Instance: The matching instance.
        """
        with _instance_api_errors():
            return self._client.cloud_instances_service_get_instance(
                id=instance_id,
                organization_id=organization_id,
            )

    def list_instances(self, organization_id: str, limit: Optional[int] = None) -> List[V1Instance]:
        """List all instances of an organization.

        Args:
            organization_id: The ID of the organization to list instances for.
            limit: The maximum number of instances to return per page.

        Returns:
            List[V1Instance]: All instances of the organization.
        """
        instances: List[V1Instance] = []
        page_token = ""
        while True:
            kwargs = {"organization_id": organization_id}
            if limit is not None:
                kwargs["limit"] = str(limit)
            if page_token:
                kwargs["page_token"] = page_token

            with _instance_api_errors():
                resp = self._client.cloud_instances_service_list_instances(**kwargs)
            instances.extend(resp.instances or [])

            page_token = resp.next_page_token or ""
            # a server that ignores paging would otherwise loop forever on the same page
            if not page_token or not resp.instances:
                return instances

    def delete_instance(self, instance_id: str, organization_id: str) -> None:
        """Delete an instance.

        Args:
            instance_id: The ID of the instance to delete.
            organization_id: The ID of the organization owning the instance.
        """
        with _instance_api_errors():
            self._client.cloud_instances_service_delete_instance(
                id=instance_id,
                organization_id=organization_id,
            )

    def list_instance_images(
        self,
        organization_id: str,
        cloud_account: Optional[str] = None,
    ) -> Tuple[List[V1InstanceImage], str]:
        """List the curated images that instances can boot from.

        Args:
            organization_id: The ID of the organization to list images for.
            cloud_account: Restrict the images to a single cloud account (cluster).

        Returns:
            Tuple[List[V1InstanceImage], str]: The available images and the default image name.
        """
        with _instance_api_errors():
            resp = self._client.cloud_instances_service_list_instance_images(
                organization_id=organization_id,
                cluster_id=cloud_account or "",
            )
        return list(resp.images or []), resp.default_image or ""

    def list_instance_types(self, organization_id: str, cloud_account: str) -> List[Tuple[str, str, float]]:
        """List the machine types a cloud account can provision instances with.

        Args:
            organization_id: The ID of the organization to list machine types for.
            cloud_account: The cloud account (cluster) to list machine types of.

        Returns:
            List[Tuple[str, str, float]]: Name, description and hourly cost of each machine type.
        """
        with _instance_api_errors():
            resp = self._client.cluster_service_list_cluster_accelerators(cloud_account, org_id=organization_id)

        types = []
        for accelerator in resp.accelerator or []:
            if accelerator.enabled is False:
                continue
            resources = accelerator.resources
            gpus = int(getattr(resources, "gpu", 0) or 0)
            cpus = int(getattr(resources, "cpu", 0) or 0)
            memory_gb = int(getattr(resources, "memory_mb", 0) or 0) // 1000
            description = f"{gpus}x {accelerator.display_name}, " if gpus else ""
            types.append(
                (
                    accelerator.instance_id or "",
                    f"{description}{cpus} CPU, {memory_gb} GB RAM",
                    float(accelerator.cost or 0),
                )
            )
        return sorted(types, key=lambda entry: entry[2])

    def list_instance_cloud_accounts(self) -> List[str]:
        """List the cloud accounts that can host instances.

        Only machine (bare-metal) cloud accounts can run plain VMs.

        Returns:
            List[str]: The IDs of all cloud accounts able to host instances.
        """
        with _instance_api_errors():
            resp = self._client.cluster_service_list_clusters()
        return [
            cluster.id
            for cluster in (resp.clusters or [])
            if cluster.spec is not None and cluster.spec.driver == _MACHINE_DRIVER
        ]
