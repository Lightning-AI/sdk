from typing import Generator, List

from lightning_sdk.api.utils import _get_registry_url
from lightning_sdk.lightning_cloud.openapi.models import V1DeleteLitRepositoryResponse
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.teamspace import Teamspace


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

    def upload_container(self, container: str, teamspace: Teamspace, tag: str) -> Generator[str, None, None]:
        import docker

        try:
            client = docker.from_env()
            client.ping()
        except docker.errors.DockerException as e:
            raise RuntimeError(f"Failed to connect to Docker daemon: {e!s}. Is Docker running?") from None

        try:
            client.images.get(container)
        except docker.errors.ImageNotFound:
            raise ValueError(f"Container {container} does not exist") from None

        registry_url = _get_registry_url()
        repository = f"{registry_url}/lit-container/{teamspace.owner.name}/{teamspace.name}/{container}"
        tagged = client.api.tag(container, repository, tag)
        if not tagged:
            raise ValueError(f"Could not tag container {container} with {repository}:{tag}")
        return client.api.push(repository, stream=True, decode=True)
