from typing import List

from lightning_sdk.lightning_cloud.rest_client import LightningClient


class LitRegistryApi:
    def __init__(self) -> None:
        self._client = LightningClient(max_tries=3)

    def list_containers(self, project_id: str) -> List:
        project = self._client.lit_registry_service_get_lit_project_registry(project_id)
        return project.repositories
