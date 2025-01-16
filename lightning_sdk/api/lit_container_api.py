from typing import List

from lightning_sdk.lightning_cloud.openapi.models import V1DeleteLitRepositoryResponse
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class LitContainerApi:
    def __init__(self) -> None:
        self._client = LightningClient(max_tries=3)

    def list_containers(self, project_id: str) -> List:
        project = self._client.lit_registry_service_get_lit_project_registry(project_id)
        return project.repositories

    def delete_container(self, project_id: str, container: str) -> V1DeleteLitRepositoryResponse:
        try:
            return self._client.lit_registry_service_delete_lit_repository(project_id, container)
        except Exception as ex:
            raise ValueError(f"Could not delete container {container} from project {project_id}") from ex
