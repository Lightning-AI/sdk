from typing import List

from lightning_sdk.lightning_cloud.rest_client import LightningClient


class LLMApi:
    def __init__(self) -> None:
        self._client = LightningClient(retry=False, max_tries=0)

    def list_models(self) -> List[str]:
        thread = self._client.assistants_service_list_assistant_managed_endpoints()
        result = thread.get()
        return result.endpoints
