"""VM deletion resolver."""

from typing import Optional

from lightning_sdk.api.vm_api import VMApi
from lightning_sdk.cli.utils.delete import DeleteAction
from lightning_sdk.cli.vm.common import friendly_error, org_id_for, resolve_teamspace, resolve_vm
from lightning_sdk.lightning_cloud.openapi.rest import ApiException


def resolve_vm_delete(name: str, teamspace: Optional[str]) -> DeleteAction:
    """Resolve a VM and return its bound deletion action."""
    resolved_teamspace = resolve_teamspace(teamspace)
    api = VMApi()
    vm = resolve_vm(api, resolved_teamspace, name)
    org_id = org_id_for(resolved_teamspace)

    def delete() -> None:
        try:
            api.delete_vm(vm.id, org_id)
        except ApiException as ex:
            raise friendly_error(ex) from ex

    return delete
