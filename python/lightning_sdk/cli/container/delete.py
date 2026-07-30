"""Container deletion resolver."""

from typing import Optional

from lightning_sdk.cli.legacy.exceptions import StudioCliError
from lightning_sdk.cli.utils.delete import DeleteAction
from lightning_sdk.cli.utils.resource_resolution import resolve_teamspace
from lightning_sdk.lit_container import LitContainer


def resolve_container_delete(
    resource_cls: type[LitContainer],
    name: str,
    teamspace: Optional[str],
) -> DeleteAction:
    """Resolve a container deletion and return its bound action."""
    resolved_teamspace = resolve_teamspace(teamspace)
    api = resource_cls()

    def delete() -> None:
        try:
            api.delete_container(
                name,
                resolved_teamspace.name,
                resolved_teamspace.owner.name,
            )
        except Exception as ex:
            raise StudioCliError(
                f"Could not delete container {name} from project {resolved_teamspace.name}: {ex}"
            ) from None

    return delete
