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
        ai_hub = AIHub()
        api_list = ai_hub.list_apis()
    """

    def __init__(self) -> None:
        self._api = AIHubApi()
        self._auth = None

    def list_apis(self, search: Optional[str] = None) -> List[Dict[str, str]]:
        """Get a list of AI Hub API templates.

        Example:
            api_hub = AIHub()
            api_list = api_hub.list_apis(search="Llama")
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
                "created_on": template.creation_timestamp.strftime("%Y-%m-%d %H:%M:%S")
                if template.creation_timestamp
                else None,
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

    def deploy(
        self,
        api_id: str,
        cluster: Optional[str] = None,
        name: Optional[str] = None,
        teamspace: Optional[Union[str, "Teamspace"]] = None,
        org: Optional[Union[str, "Organization"]] = None,
        **kwargs: Dict[str, Any],
    ) -> Dict[str, Union[str, bool]]:
        """Deploy an API from the AI Hub.

        Example:
            from lightning_sdk import AIHub
            ai_hub = AIHub()
            deployment = ai_hub.deploy("temp_01jc37n6qpqkdptjpyep0z06hy", batch_size=10)

        Args:
            api_id: The ID of the API you want to deploy.
            cluster: The cluster where you want to deploy the API, such as "lightning-public-prod".
            name: Name for the deployed API. Defaults to None.
            teamspace: The team or group for deployment. Defaults to None.
            org: The organization for deployment. Defaults to None.
            **kwargs: Additional keyword arguments for deployment.

        Returns:
            A dictionary containing the name of the deployed API,
            the URL to access it, and whether it is interruptible.

        Raises:
            ValueError: If a teamspace or organization is not provided.
            ConnectionError: If there is an issue with logging in.
        """
        teamspace = self._authenticate(teamspace, org)
        teamspace_id = teamspace.id

        deployment = self._api.deploy_api(
            template_id=api_id, cluster_id=cluster, project_id=teamspace_id, name=name, **kwargs
        )
        url = quote(f"{LIGHTNING_CLOUD_URL}/{teamspace._org.name}/{teamspace.name}/jobs/{deployment.name}", safe=":/()")
        print("Deployment available at:", url)
        return {
            "id": deployment.id,
            "name": deployment.name,
            "base_url": deployment.status.urls[0],
            "interruptible": deployment.spec.spot,
        }
