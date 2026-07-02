from typing import Any, List, Optional

from lightning_sdk.lightning_cloud.openapi import (
    CloudSpaceEnvironmentTemplateServiceUpdateCloudSpaceEnvironmentTemplateBody as BaseStudioUpdateBody,
)
from lightning_sdk.lightning_cloud.openapi import (
    V1CloudSpaceEnvironmentType,
    V1ListCloudSpaceEnvironmentTemplatesResponse,
)
from lightning_sdk.lightning_cloud.openapi.models.v1_cloud_space_environment_template import (
    V1CloudSpaceEnvironmentTemplate,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class BaseStudioApi:
    """Internal API client for base studio (environment template) operations."""

    def __init__(self) -> None:
        self._client = LightningClient(retry=False, max_tries=0)

    def get_base_studio(self, base_studio_id: str, org_id: Optional[str] = None) -> V1CloudSpaceEnvironmentTemplate:
        """Retrieve the base studio by its ID.

        Args:
            base_studio_id: The unique ID of the base studio to retrieve.
            org_id: The organisation ID context for the lookup; defaults to empty string when ``None``.

        Returns:
            V1CloudSpaceEnvironmentTemplate: The matching base studio template.

        Raises:
            ValueError: If no base studio with the given ID exists.
        """
        try:
            return self._client.cloud_space_environment_template_service_get_cloud_space_environment_template(
                base_studio_id, org_id=org_id or ""
            )
        except ValueError as e:
            raise ValueError(f"Base studio {base_studio_id} does not exist") from e

    def get_all_base_studios(self, org_id: Optional[str]) -> V1ListCloudSpaceEnvironmentTemplatesResponse:
        """Retrieve all base studios for a given organization.

        Args:
            org_id: The organisation ID to list base studios for; if ``None``, only managed templates are returned.

        Returns:
            V1ListCloudSpaceEnvironmentTemplatesResponse: Combined list of managed and org-specific templates.
        """
        result = self._client.cloud_space_environment_template_service_list_managed_cloud_space_environment_templates(
            org_id=org_id or ""
        )
        if org_id is not None:
            org_templates = (
                self._client.cloud_space_environment_template_service_list_cloud_space_environment_templates(
                    org_id=org_id
                )
            )
            result.templates = result.templates + org_templates.templates
        return result

    def update_base_studio(
        self,
        base_studio_id: str,
        org_id: str,
        name: Optional[str] = None,
        allowed_machines: Optional[List[str]] = None,
        default_machine: Optional[str] = None,
        disabled: Optional[bool] = None,
        environment_type: Optional[V1CloudSpaceEnvironmentType] = None,
        machine_image_version: Optional[str] = None,
        setup_script_text: Optional[str] = None,
    ) -> V1CloudSpaceEnvironmentTemplate:
        """Patch a base studio environment template; only non-``None`` arguments are applied.

        Args:
            base_studio_id: The unique ID of the base studio to update.
            org_id: The organisation that owns the base studio.
            name: New display name for the template.
            allowed_machines: Updated list of allowed machine types.
            default_machine: New default machine type.
            disabled: Whether the template should be disabled.
            environment_type: New environment type for the template.
            machine_image_version: New machine image version string.
            setup_script_text: New setup script content.

        Returns:
            V1CloudSpaceEnvironmentTemplate: The updated base studio template.
        """
        base_studio = self.get_base_studio(base_studio_id, org_id)

        # Get the current configuration for the base studio
        update_body = BaseStudioUpdateBody(
            org_id=base_studio.org_id,
            name=base_studio.name,
            allowed_machines=base_studio.config.allowed_machines,
            default_machine=base_studio.config.default_machine,
            environment_type=base_studio.config.environment_type,
            machine_image_version=base_studio.config.machine_image_version,
            setup_script_text=base_studio.config.setup_script_text,
            disabled=base_studio.disabled,
        )

        # Apply changes only if the new value is not None
        apply_change(update_body, "name", name)
        apply_change(update_body, "allowed_machines", allowed_machines)
        apply_change(update_body, "default_machine", default_machine)
        apply_change(update_body, "environment_type", environment_type)
        apply_change(update_body, "machine_image_version", machine_image_version)
        apply_change(update_body, "setup_script_text", setup_script_text)
        apply_change(update_body, "disabled", disabled)

        return self._client.cloud_space_environment_template_service_update_cloud_space_environment_template(
            id=base_studio_id,
            body=update_body,
        )


def apply_change(spec: Any, key: str, value: Any) -> bool:
    """Set ``key`` on ``spec`` to ``value`` if ``value`` is not ``None`` and differs from the current value.

    Args:
        spec: The object whose attribute to update.
        key: The attribute name to set.
        value: The new value; no-op when ``None``.

    Returns:
        ``True`` if the attribute was changed, ``False`` otherwise.
    """
    if value is None:
        return False

    if getattr(spec, key) != value:
        setattr(spec, key, value)
        return True

    return False
