from dataclasses import dataclass
from typing import List, Optional, Union

from lightning_sdk.api.base_studio_api import BaseStudioApi
from lightning_sdk.api.user_api import UserApi
from lightning_sdk.lightning_cloud import login
from lightning_sdk.lightning_cloud.openapi.models.v1_cloud_space_environment_type import V1CloudSpaceEnvironmentType
from lightning_sdk.organization import Organization
from lightning_sdk.user import User
from lightning_sdk.utils.resolve import _resolve_org, _resolve_user


@dataclass
class BaseStudioInfo:
    id: str
    name: str
    managed_id: str
    description: str


class BaseStudio:
    def __init__(
        self,
        name: Optional[str] = None,
        org: Optional[Union[str, Organization]] = None,
        user: Optional[Union[str, User]] = None,
    ) -> None:
        """Initializes the BaseStudio instance with organization and user information.

        Args:
            org (Optional[Union[str, Organization]]): The organization for the base studio. If not provided,
                                                      it will be resolved through the authentication process.
            user (Optional[Union[str, User]]): The user for the base studio. If not provided, it will be resolved
                                               through the authentication process.

        Raises:
            ConnectionError: If there is an issue with the authentication process.
        """
        self._auth = login.Auth()
        self._user = None

        try:
            self._auth.authenticate()
            if user is None:
                self._user = User(name=UserApi()._get_user_by_id(self._auth.user_id).username)
        except ConnectionError as e:
            raise e

        self._user = _resolve_user(self._user or user)
        self._org = _resolve_org(org)

        self._base_studio_api = BaseStudioApi()

        if name is not None:
            base_studio = self._base_studio_api.get_base_studio(name, self._org.id)

            if base_studio is None:
                raise ValueError(f"Base studio with name {name} does not exist in organization {self._org.name}")
            self._base_studio = base_studio

    def update(
        self,
        name: Optional[str] = None,
        allowed_machines: Optional[List[str]] = None,
        default_machine: Optional[str] = None,
        disabled: Optional[bool] = None,
        environment_type: Optional[V1CloudSpaceEnvironmentType] = None,
        machine_image_version: Optional[str] = None,
        setup_script_text: Optional[str] = None,
    ) -> None:
        self._base_studio = self._base_studio_api.update_base_studio(
            self._base_studio.id,
            self._org.id,
            name=name,
            allowed_machines=allowed_machines,
            default_machine=default_machine,
            environment_type=environment_type,
            machine_image_version=machine_image_version,
            setup_script_text=setup_script_text,
            disabled=disabled,
        )

    def list(self, managed: bool = True) -> List[BaseStudioInfo]:
        """List all base studios in the organization.

        Returns:
            List[V1CloudSpaceEnvironmentTemplate]: A list of base studio templates.
        """
        result = []
        for template in self._base_studio_api.get_all_base_studios(self._org.id, managed).templates:
            result.append(
                BaseStudioInfo(
                    id=template.id,
                    name=template.name,
                    managed_id=template.managed_id,
                    description=template.description,
                ),
            )
        return result
