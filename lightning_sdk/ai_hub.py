from typing import Dict, List

from lightning_sdk.api.ai_hub_api import AIHubApi


class AIHub:
    """An interface to interact with the AI Hub.

    Example:
        ai_hub = AIHub()
        api_list = ai_hub.list_apis()
    """

    def __init__(self) -> None:
        self._api = AIHubApi()

    def list_apis(self) -> List[Dict[str, str]]:
        """Get a list of AI Hub API templates."""
        api_templates = self._api.list_apis()
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
