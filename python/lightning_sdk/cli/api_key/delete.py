"""API-key deletion resolver."""

from functools import partial
from typing import Optional

from lightning_sdk.api.api_key_api import ApiKeyApi
from lightning_sdk.cli.api_key.common import resolve_org
from lightning_sdk.cli.utils.delete import DeleteAction


def resolve_api_key_delete(
    resource_cls: type[ApiKeyApi],
    key_id: str,
    org_name: Optional[str],
) -> DeleteAction:
    """Resolve an API key and return its bound deletion action."""
    organization = resolve_org(org_name)
    api = resource_cls()
    return partial(api.delete, organization.id, key_id)
