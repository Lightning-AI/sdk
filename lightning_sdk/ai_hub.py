from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
from urllib.parse import quote

from lightning_sdk.api import AIHubApi, UserApi
from lightning_sdk.lightning_cloud import login
from lightning_sdk.lightning_cloud.env import LIGHTNING_CLOUD_URL
from lightning_sdk.user import User
from lightning_sdk.utils.resolve import _resolve_org, _resolve_teamspace

if TYPE_CHECKING:
    from lightning_sdk import Organization, Teamspace


class AIHub:
    """An interface to interact with the AI Hub.

    Example:
        from lightning_sdk import AIHub
        hub = AIHub()

        # List public API templates
        api_list = hub.list_apis()

        # Get detailed information about an API template
        api_info =  hub.api_info("temp_xxxx")

        # Deploy an API template
        deployment = hub.deploy("temp_xxxx")
    """

    def __init__(self) -> None:
        self._api = AIHubApi()
        self._auth = None

    def api_info(self, api_id: str) -> dict:
        """Get full API template info such as input details.

        Example:
            ai_hub = AIHub()
            api_info = ai_hub.api_info("temp_xxxx")

        Args:
            api_id: The ID of the API for which information is requested.

        Returns:
            A dictionary containing detailed information about the API,
            including its name, description, creation and update timestamps,
            parameters, tags, job specifications, and autoscaling settings.
        """
        template, api_arguments = self._api.api_info(api_id)

        return {
            "name": template.name,
            "description": template.description,
            "created_at": template.created_at,
            "updated_at": template.updated_at,
            "api_arguments": api_arguments,
            "tags": [tag.name for tag in template.tags],
            "job": {
                "image": template.spec_v2.job.image,
                "interruptible": template.spec_v2.job.spot,
                "instance_type": template.spec_v2.job.instance_type,
                "resources": template.spec_v2.job.resources,
            },
            "autoscaling": {
                "enabled": template.spec_v2.autoscaling.enabled,
                "min_replicas": template.spec_v2.autoscaling.min_replicas,
                "max_replicas": template.spec_v2.autoscaling.max_replicas,
            },
        }

    def list_apis(
        self,
        search: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Get a list of public AI Hub API templates.

        Example:
            ai_hub = AIHub()
            api_list = ai_hub.list_apis(search="Llama")

        Args:
            search: A search query to filter the list of APIs. Defaults to None.

        Returns:
            A list of dictionaries, each containing information about an API,
            such as its ID, name, description, creator's username, and creation timestamp.
        """
        search_query = search or ""
        api_templates = self._api.list_apis(search_query=search_query)
        results = []
        for template in api_templates:
            result = {
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "creator_username": template.creator_username,
            }
            results.append(result)
        return results

    def _authenticate(
        self,
        teamspace: Optional[Union[str, "Teamspace"]] = None,
        org: Optional[Union[str, "Organization"]] = None,
        user: Optional[Union[str, "User"]] = None,
    ) -> "Teamspace":
        if self._auth is None:
            self._auth = login.Auth()
        try:
            self._auth.authenticate()
            user = User(name=UserApi()._get_user_by_id(self._auth.user_id).username)
        except ConnectionError as e:
            raise e

        org = _resolve_org(org)
        teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user if org is None else None)
        if teamspace is None:
            raise ValueError("You need to pass a teamspace or an org for your deployment.")
        return teamspace

    def run(
        self,
        api_id: str,
        api_arguments: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        cloud_account: Optional[str] = None,
        teamspace: Optional[Union[str, "Teamspace"]] = None,
        org: Optional[Union[str, "Organization"]] = None,
    ) -> Dict[str, Union[str, bool]]:
        """Deploy an API from the AI Hub.

        Example:
            from lightning_sdk import AIHub
            hub = AIHub()
            deployment = hub.run("temp_xxxx")

            # Using API arguments
            api_arugments = {"model": "unitary/toxic-bert", "batch_size": 10, "token": "lit_xxxx"}
            deployment = hub.run("temp_xxxx", api_arugments=api_arugments)

        Args:
            api_id: The ID of the AIHub template you want to run.
            api_arguments: Additional API argument, such as model name, or batch size.
            name: Name for the deployed API. Defaults to None.
            cloud_account: The cloud account where you want to run the template, such as "lightning-public-prod".
                Defaults to None.
            teamspace: The team or group for deployment. Defaults to None.
            org: The organization for deployment. Defaults to None.

        Returns:
            A dictionary containing the name of the deployed API,
            the URL to access it, and whether it is interruptible.

        Raises:
            ValueError: If a teamspace or organization is not provided.
            ConnectionError: If there is an issue with logging in.
        """
        teamspace = self._authenticate(teamspace, org)
        teamspace_id = teamspace.id

        api_arguments = api_arguments or {}
        deployment = self._api.run_api(
            template_id=api_id,
            cloud_account=cloud_account or "",
            project_id=teamspace_id,
            name=name,
            api_arguments=api_arguments,
        )
        url = (
            quote(
                f"{LIGHTNING_CLOUD_URL}/{teamspace._org.name}/{teamspace.name}/jobs/{deployment.name}",
                safe=":/()",
            )
            + "?app_id=deployment"
        )
        print("Deployment available at:", url)

        return {
            "id": deployment.id,
            "name": deployment.name,
            "deployment_url": url,
            "api_endpoint": deployment.status.urls[0],
            "interruptible": deployment.spec.spot,
        }
