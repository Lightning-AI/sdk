from typing import Any, Callable, Generator, List

import docker
import requests

from lightning_sdk.api.utils import _get_registry_url
from lightning_sdk.lightning_cloud.env import LIGHTNING_CLOUD_URL
from lightning_sdk.lightning_cloud.openapi.models import V1DeleteLitRepositoryResponse
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.teamspace import Teamspace


class LCRAuthFailedError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "Failed to authenticate with Lightning Container Registry. Please login manually "
            "using the following command:\n  "
            "echo $LIGHTNING_API_KEY | docker login litcr.io --username=LIGHTNING_USERNAME --password-stdin"
        )


def retry_on_lcr_auth_failure(func: Callable) -> Callable:
    def wrapper(self: "LitContainerApi", *args: Any, **kwargs: Any) -> Callable:
        try:
            return func(self, *args, **kwargs)
        except LCRAuthFailedError:
            self.authenticate()
            return func(self, *args, **kwargs)

    return wrapper


class LitContainerApi:
    def __init__(self) -> None:
        self._client = LightningClient(max_tries=3)

        try:
            self._docker_client = docker.from_env()
            self._docker_client.ping()
        except docker.errors.DockerException as e:
            raise RuntimeError(f"Failed to connect to Docker daemon: {e!s}. Is Docker running?") from None

    def authenticate(self) -> bool:
        authed_user = self._client.auth_service_get_user()
        username = authed_user.username
        api_key = authed_user.api_key
        resp = self._docker_client.login(username, password=api_key, registry=_get_registry_url())
        return resp["Status"] == "Login Succeeded"

    def list_containers(self, project_id: str) -> List:
        project = self._client.lit_registry_service_get_lit_project_registry(project_id)
        return project.repositories

    def delete_container(self, project_id: str, container: str) -> V1DeleteLitRepositoryResponse:
        try:
            return self._client.lit_registry_service_delete_lit_repository(project_id, container)
        except Exception as e:
            raise ValueError(f"Could not delete container {container} from project {project_id}: {e!s}") from e

    def upload_container(self, container: str, teamspace: Teamspace, tag: str) -> Generator[dict, None, None]:
        try:
            self._docker_client.images.get(container)
        except docker.errors.ImageNotFound:
            raise ValueError(f"Container {container} does not exist") from None

        registry_url = _get_registry_url()
        container_basename = container.split("/")[-1]
        repository = f"{registry_url}/lit-container/{teamspace.owner.name}/{teamspace.name}/{container_basename}"
        tagged = self._docker_client.api.tag(container, repository, tag)
        if not tagged:
            raise ValueError(f"Could not tag container {container} with {repository}:{tag}")
        lines = self._docker_client.api.push(repository, stream=True, decode=True)
        for line in lines:
            if "errorDetail" in line and ("authorization failed" in line["error"] or "unauth" in line["error"]):
                raise LCRAuthFailedError()
            yield line
        yield {
            "finish": True,
            "url": f"{LIGHTNING_CLOUD_URL}/{teamspace.owner.name}/{teamspace.name}/containers/{container_basename}",
        }

    @retry_on_lcr_auth_failure
    def download_container(self, container: str, teamspace: Teamspace, tag: str) -> Generator[str, None, None]:
        registry_url = _get_registry_url()
        repository = f"{registry_url}/lit-container/{teamspace.owner.name}/{teamspace.name}/{container}"
        try:
            self._docker_client.images.pull(repository, tag=tag)
        except requests.exceptions.HTTPError as e:
            if "unauthorized" in e.response.text:
                raise LCRAuthFailedError() from e
        except docker.errors.APIError as e:
            raise ValueError(f"Could not pull container {container} from {repository}:{tag}") from e
        return self._docker_client.api.tag(repository, container, tag)
