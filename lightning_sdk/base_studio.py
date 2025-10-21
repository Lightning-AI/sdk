from dataclasses import dataclass
from typing import List, Optional, Union

from lightning_sdk.api.base_studio_api import BaseStudioApi
from lightning_sdk.api.user_api import UserApi
from lightning_sdk.lightning_cloud.openapi.models.v1_cloud_space_environment_type import V1CloudSpaceEnvironmentType
from lightning_sdk.organization import Organization
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User
from lightning_sdk.utils.resolve import _resolve_teamspace


@dataclass
class BaseStudioInfo:
    id: str
    name: str
    managed_id: str
    description: str
    creator: str
    enabled: bool


class BaseStudio:
    def __init__(
        self,
        name: Optional[str] = None,
        teamspace: Optional[Union[str, Teamspace]] = None,
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
        self._teamspace = None

        _teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
        if _teamspace is None:
            raise ValueError("Couldn't resolve teamspace from the provided name, org, or user")

        self._teamspace = _teamspace

        # self._auth = login.Auth()
        # self._user = None

        # try:
        #     self._auth.authenticate()
        #     if user is None:
        #         self._user = User(name=UserApi()._get_user_by_id(self._auth.user_id).username)
        # except ConnectionError as e:
        #     raise e

        # self._user = _resolve_user(self._user or user)
        # self._org = _resolve_org(org)

        self._base_studio_api = BaseStudioApi()

        if name is not None:
            org_id = self._teamspace._org.id if self._teamspace._org is not None else None
            base_studio = self._base_studio_api.get_base_studio(name, org_id)

            if base_studio is None:
                raise ValueError(f"Base studio with name {name} does not exist")
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
        org_id = self._teamspace._org.id if self._teamspace._org is not None else None
        # TODO: if not in an org, can't update them
        self._base_studio = self._base_studio_api.update_base_studio(
            self._base_studio.id,
            org_id,
            name=name,
            allowed_machines=allowed_machines,
            default_machine=default_machine,
            environment_type=environment_type,
            machine_image_version=machine_image_version,
            setup_script_text=setup_script_text,
            disabled=disabled,
        )

    def list(self, include_disabled: bool = False) -> List[BaseStudioInfo]:
        """List all base studios in the organization.

        Args:
            managed: Whether to filter for managed base studios.
            include_disabled: Whether to include disabled base studios in the results.

        Returns:
            List[BaseStudioInfo]: A list of base studio templates.
        """
        org_id = self._teamspace._org.id if self._teamspace._org is not None else None
        templates = self._base_studio_api.get_all_base_studios(org_id).templates

        return [
            BaseStudioInfo(
                id=template.id,
                name=template.name,
                managed_id=template.managed_id,
                description=template.description,
                creator="⚡ Lightning AI"
                if template.managed_id
                else UserApi()._get_user_by_id(template.user_id).username,
                enabled=not template.disabled,
            )
            for template in templates
            if include_disabled or not template.disabled
        ]
