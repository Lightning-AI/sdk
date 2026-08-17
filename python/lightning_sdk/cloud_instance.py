"""Plain cloud VMs (instances) managed through Lightning."""

import subprocess
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, NamedTuple, Optional, Sequence, Union

from lightning_sdk.api.instance_api import InstanceApi
from lightning_sdk.lightning_cloud.openapi import V1Instance
from lightning_sdk.utils.resolve import _resolve_org_id

if TYPE_CHECKING:
    from lightning_sdk.machine import Machine
    from lightning_sdk.organization import Organization

__all__ = [
    "CloudInstance",
    "InstanceImage",
    "InstanceType",
]

#: Status of an instance that is up and reachable over SSH.
STATUS_RUNNING = "running"
#: Status of an instance that will never become running.
STATUS_FAILED = "failed"
#: Status of an instance whose spot capacity was reclaimed by the cloud provider.
STATUS_RECLAIMED = "reclaimed"
#: Status of an instance that is being torn down.
STATUS_DELETING = "deleting"

_TERMINAL_STATUSES = (STATUS_FAILED, STATUS_RECLAIMED, STATUS_DELETING)


class InstanceImage(NamedTuple):
    """A curated OS image an instance can boot from."""

    name: str
    description: str


class InstanceType(NamedTuple):
    """A machine type an instance can run on."""

    name: str
    description: str
    #: On-demand price in USD per hour.
    cost: float


class CloudInstance:
    """A plain cloud VM.

    Unlike Studios and Jobs, an instance is a raw virtual machine: Lightning provisions
    it, injects the SSH keys of your Lightning account and gets out of the way. Nothing
    is installed on it beyond what the image (and your ``cloud_init``) brings.

    Args:
        name_or_id: The ID or the name of an existing instance to look up.
        org: The organization owning the instance. Resolved from the environment if omitted.

    Note:
        Instances are owned by an organization, not by a teamspace. They are not
        persisted: deleting one destroys its volume with it.

    Example::

        instance = CloudInstance.create(
            name="my-vm",
            instance_type="cpu-4",
            ports=[8080],
            wait=True,
        )
        print(instance.ssh_command)

    """

    def __init__(
        self,
        name_or_id: Optional[str] = None,
        org: Optional[Union[str, "Organization"]] = None,
    ) -> None:
        self._api = InstanceApi()
        self._org_id = _resolve_org_id(org)
        self._instance: Optional[V1Instance] = None

        if name_or_id is not None:
            self._instance = self._fetch(name_or_id)

    @classmethod
    def create(
        cls,
        name: str,
        instance_type: Union[str, "Machine"],
        cloud_account: Optional[str] = None,
        org: Optional[Union[str, "Organization"]] = None,
        volume_size: Optional[int] = None,
        spot: bool = False,
        ports: Optional[Sequence[Union[int, str]]] = None,
        image: Optional[str] = None,
        cloud_init: Optional[str] = None,
        wait: bool = False,
        timeout: float = 900,
    ) -> "CloudInstance":
        """Create a new cloud instance.

        Args:
            name: The name of the instance.
            instance_type: The machine type to provision, e.g. ``cpu-4``. See :meth:`instance_types`.
            cloud_account: The cloud account to create the instance on.
                Defaults to the only cloud account able to host instances.
            org: The organization owning the instance. Resolved from the environment if omitted.
            volume_size: The root volume size in GB. Defaults to the cloud account's minimum.
            spot: Whether to request an interruptible (spot) instance.
            ports: Ports to expose on the instance in addition to SSH.
            image: A curated image name from :meth:`images`. Defaults to the cloud account's image.
            cloud_init: Raw ``#cloud-config`` YAML to apply at boot.
            wait: Whether to block until the instance is running.
            timeout: How many seconds to wait for the instance when ``wait`` is set.

        Returns:
            CloudInstance: The newly created instance.
        """
        self = cls(org=org)
        resolved_account = cloud_account or self._default_cloud_account()

        self._instance = self._api.create_instance(
            name=name,
            organization_id=self._org_id,
            cloud_account=resolved_account,
            instance_type=str(instance_type),
            volume_size=volume_size,
            spot=spot,
            ports=[int(port) for port in ports] if ports else None,
            image=image,
            cloud_init=cloud_init,
        )
        if wait:
            self.wait_until_running(timeout=timeout)
        return self

    @classmethod
    def list(
        cls,
        org: Optional[Union[str, "Organization"]] = None,
        limit: Optional[int] = None,
    ) -> List["CloudInstance"]:
        """List all instances of an organization.

        Args:
            org: The organization to list instances for. Resolved from the environment if omitted.
            limit: The maximum number of instances to fetch per request.

        Returns:
            List[CloudInstance]: All instances of the organization.
        """
        self = cls(org=org)
        instances = self._api.list_instances(organization_id=self._org_id, limit=limit)

        resolved = []
        for instance in instances:
            other = cls.__new__(cls)
            other._api = self._api
            other._org_id = self._org_id
            other._instance = instance
            resolved.append(other)
        return resolved

    @classmethod
    def images(
        cls,
        cloud_account: Optional[str] = None,
        org: Optional[Union[str, "Organization"]] = None,
    ) -> List[InstanceImage]:
        """List the curated images instances can boot from.

        Args:
            cloud_account: Restrict the images to a single cloud account.
            org: The organization to list images for. Resolved from the environment if omitted.

        Returns:
            List[InstanceImage]: The available images. The default image is listed first.
        """
        self = cls(org=org)
        images, default_image = self._api.list_instance_images(
            organization_id=self._org_id,
            cloud_account=cloud_account,
        )
        resolved = [InstanceImage(name=image.name or "", description=image.description or "") for image in images]
        resolved.sort(key=lambda image: (image.name != default_image, image.name))
        return resolved

    @classmethod
    def instance_types(
        cls,
        cloud_account: Optional[str] = None,
        org: Optional[Union[str, "Organization"]] = None,
    ) -> List["InstanceType"]:
        """List the machine types instances can run on, cheapest first.

        Args:
            cloud_account: The cloud account to list machine types of. Defaults to the only
                cloud account able to host instances.
            org: The organization to list machine types for. Resolved from the environment if omitted.

        Returns:
            List[InstanceType]: The available machine types.
        """
        self = cls(org=org)
        types = self._api.list_instance_types(
            organization_id=self._org_id,
            cloud_account=cloud_account or self._default_cloud_account(),
        )
        return [InstanceType(name=name, description=description, cost=cost) for name, description, cost in types]

    @classmethod
    def cloud_accounts(cls) -> List[str]:
        """List the cloud accounts able to host instances.

        Returns:
            List[str]: The IDs of all cloud accounts able to host instances.
        """
        return InstanceApi().list_instance_cloud_accounts()

    @property
    def id(self) -> str:
        """The instance's ID."""
        return self._get().id or ""

    @property
    def name(self) -> str:
        """The instance's name."""
        return self._get().name or ""

    @property
    def organization_id(self) -> str:
        """The ID of the organization owning the instance."""
        return self._get().organization_id or ""

    @property
    def cloud_account(self) -> str:
        """The cloud account the instance runs on."""
        return self._get().cluster_id or ""

    @property
    def instance_type(self) -> str:
        """The machine type of the instance."""
        return self._get().instance_type or ""

    @property
    def volume_size(self) -> int:
        """The root volume size in GB."""
        return int(self._get().volume_size or 0)

    @property
    def spot(self) -> bool:
        """Whether the instance is interruptible."""
        return bool(self._get().spot)

    @property
    def status(self) -> str:
        """The instance's status, one of pending, provisioning, running, failed, reclaimed, deleting."""
        return self._refresh().status or ""

    @property
    def status_reason(self) -> str:
        """Why the instance failed, if it did."""
        return self._get().status_reason or ""

    @property
    def region(self) -> str:
        """The region the instance runs in."""
        return self._get().region or ""

    @property
    def availability_zone(self) -> str:
        """The availability zone the instance runs in."""
        return self._get().availability_zone or ""

    @property
    def ports(self) -> List[int]:
        """The ports exposed on the instance in addition to SSH."""
        return [int(port) for port in (self._get().ports or [])]

    @property
    def image(self) -> str:
        """The image the instance booted from."""
        return self._get().image or ""

    @property
    def ssh_user(self) -> str:
        """The user to connect as. Empty until the instance is running."""
        return self._refresh().ssh_user or ""

    @property
    def ssh_host(self) -> str:
        """The instance's public address. Empty until the instance is running."""
        return self._refresh().ssh_host or ""

    @property
    def ssh_port(self) -> int:
        """The port the instance's SSH daemon is reachable on. Zero until the instance is running."""
        return int(self._refresh().ssh_port or 0)

    @property
    def ssh_command(self) -> str:
        """The ready-to-run SSH command for this instance. Empty until the instance is running."""
        return self._refresh().ssh_command or ""

    @property
    def created_at(self) -> Optional[datetime]:
        """When the instance was created."""
        return self._get().created_at

    @property
    def started_at(self) -> Optional[datetime]:
        """When the instance started running."""
        return self._get().started_at

    @property
    def updated_at(self) -> Optional[datetime]:
        """When the instance was last updated."""
        return self._get().updated_at

    @property
    def user_id(self) -> str:
        """The ID of the user who created the instance."""
        return self._get().user_id or ""

    def wait_until_running(self, timeout: float = 900, poll_interval: float = 5) -> "CloudInstance":
        """Block until the instance is running.

        Args:
            timeout: How many seconds to wait before giving up.
            poll_interval: How many seconds to sleep between status checks.

        Returns:
            CloudInstance: The instance itself, so calls can be chained.

        Raises:
            RuntimeError: If the instance failed or was reclaimed.
            TimeoutError: If the instance was not running within ``timeout`` seconds.
        """
        deadline = time.monotonic() + timeout
        while True:
            instance = self._refresh()
            status = instance.status or ""
            # ssh_command only appears once the SSH port forward exists, which can lag the
            # running status by a few seconds. Waiting for it keeps `wait=True` connectable.
            if status == STATUS_RUNNING and instance.ssh_command:
                return self
            if status in _TERMINAL_STATUSES:
                reason = instance.status_reason or ""
                raise RuntimeError(f"Instance {self.name} is {status}{f': {reason}' if reason else ''}")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Instance {self.name} is still {status or 'pending'} after {timeout} seconds")
            time.sleep(poll_interval)

    def ssh(self, command: Optional[Union[str, Sequence[str]]] = None, options: Optional[Sequence[str]] = None) -> int:
        """Open an SSH session to the instance, or run a single command on it.

        Uses the Lightning-managed SSH key, downloading it if needed.

        Args:
            command: A command to run on the instance. Opens an interactive shell if omitted.
            options: Additional ``-o`` options to pass to ``ssh``.

        Returns:
            int: The exit code of the ``ssh`` process.

        Raises:
            RuntimeError: If the instance is not reachable over SSH yet.
        """
        return subprocess.run(self.ssh_args(command=command, options=options), check=False).returncode

    def ssh_args(
        self,
        command: Optional[Union[str, Sequence[str]]] = None,
        options: Optional[Sequence[str]] = None,
        key_path: Optional[str] = None,
    ) -> List[str]:
        """Build the ``ssh`` argument list used to reach this instance.

        Args:
            command: A command to run on the instance. Opens an interactive shell if omitted.
            options: Additional ``-o`` options to pass to ``ssh``.
            key_path: The private key to authenticate with. Defaults to the Lightning-managed key.

        Returns:
            List[str]: The full ``ssh`` command as an argument list.

        Raises:
            RuntimeError: If the instance is not reachable over SSH yet.
        """
        instance = self._refresh()
        if not instance.ssh_host or not instance.ssh_port:
            status = instance.status or "pending"
            raise RuntimeError(
                f"Instance {self.name} is {status} and has no SSH endpoint yet. "
                "Wait for it to be running (see wait_until_running)."
            )

        if key_path is None:
            from lightning_sdk.cli.utils.ssh_connection import configure_ssh_internal

            key_path = configure_ssh_internal()

        args = ["ssh", "-i", key_path, "-p", str(instance.ssh_port)]
        for option in options or []:
            args.extend(["-o", option])
        args.append(f"{instance.ssh_user or 'ubuntu'}@{instance.ssh_host}")
        if command:
            args.extend([command] if isinstance(command, str) else list(command))
        return args

    def delete(self) -> None:
        """Delete the instance and its volume."""
        self._api.delete_instance(instance_id=self.id, organization_id=self._org_id)

    def refresh(self) -> "CloudInstance":
        """Re-fetch the instance from the API.

        Returns:
            CloudInstance: The instance itself, so calls can be chained.
        """
        self._refresh()
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Return the instance as a plain dictionary.

        Uses the last known state; call :meth:`refresh` first for a live snapshot.

        Returns:
            Dict[str, Any]: All fields of the instance.
        """
        instance = self._get()
        return {
            "id": instance.id or "",
            "name": instance.name or "",
            "organization_id": instance.organization_id or "",
            "cloud_account": instance.cluster_id or "",
            "instance_type": instance.instance_type or "",
            "volume_size": int(instance.volume_size or 0),
            "spot": bool(instance.spot),
            "status": instance.status or "",
            "status_reason": instance.status_reason or "",
            "region": instance.region or "",
            "availability_zone": instance.availability_zone or "",
            "ports": [int(port) for port in (instance.ports or [])],
            "image": instance.image or "",
            "ssh_user": instance.ssh_user or "",
            "ssh_host": instance.ssh_host or "",
            "ssh_port": int(instance.ssh_port or 0),
            "ssh_command": instance.ssh_command or "",
            "user_id": instance.user_id or "",
            "created_at": instance.created_at,
            "started_at": instance.started_at,
            "updated_at": instance.updated_at,
        }

    def _default_cloud_account(self) -> str:
        accounts = self._api.list_instance_cloud_accounts()
        if len(accounts) == 1:
            return accounts[0]
        if not accounts:
            raise ValueError("No cloud account available for instances. Please contact support.")
        raise ValueError(
            f"Multiple cloud accounts can host instances, so it can't be inferred. "
            f"Specify one of: {', '.join(sorted(accounts))}"
        )

    def _fetch(self, name_or_id: str) -> V1Instance:
        try:
            return self._api.get_instance(instance_id=name_or_id, organization_id=self._org_id)
        except (ValueError, RuntimeError) as e:
            # the API only looks resources up by ID, so an unknown one may still be a name
            if "not found" not in str(e).lower():
                raise

        matches = [i for i in self._api.list_instances(organization_id=self._org_id) if i.name == name_or_id]
        if not matches:
            raise ValueError(f"Instance {name_or_id} does not exist")
        if len(matches) > 1:
            ids = ", ".join(sorted(i.id for i in matches))
            raise ValueError(f"Multiple instances are named {name_or_id}. Specify one by ID: {ids}")
        return matches[0]

    def _get(self) -> V1Instance:
        if self._instance is None:
            raise RuntimeError("No instance is bound to this object. Use CloudInstance.create() or pass a name or ID.")
        return self._instance

    def _refresh(self) -> V1Instance:
        instance = self._get()
        self._instance = self._api.get_instance(instance_id=instance.id, organization_id=self._org_id)
        return self._instance

    def __repr__(self) -> str:
        """Returns reader friendly representation."""
        if self._instance is None:
            return "CloudInstance(unbound)"
        return f"CloudInstance(name={self.name}, id={self._instance.id}, status={self._instance.status})"

    def __eq__(self, other: object) -> bool:
        """Two instances are equal if they have the same ID."""
        if not isinstance(other, CloudInstance) or self._instance is None or other._instance is None:
            return False
        return self._instance.id == other._instance.id

    def __hash__(self) -> int:
        """Hashes by the instance's ID."""
        return hash(None if self._instance is None else self._instance.id)
