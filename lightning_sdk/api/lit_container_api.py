import inspect
import time
from typing import Any, Callable, Dict, Generator, Iterator, List

import docker
import requests

from lightning_sdk.api.utils import _get_registry_url
from lightning_sdk.lightning_cloud.env import LIGHTNING_CLOUD_URL
from lightning_sdk.lightning_cloud.openapi.models import V1DeleteLitRepositoryResponse
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.teamspace import Teamspace


class LCRAuthFailedError(Exception):
    def __init__(self) -> None:
        super().__init__("Failed to authenticate with Lightning Container Registry. Please try again.")


class DockerPushError(Exception):
    pass


def retry_on_lcr_auth_failure(func: Callable) -> Callable:
    def generator_wrapper(self: "LitContainerApi", *args: Any, **kwargs: Any) -> Callable:
        try:
            gen = func(self, *args, **kwargs)
            yield from gen
        except LCRAuthFailedError:
            self.authenticate(reauth=True)
            gen = func(self, *args, **kwargs)
            yield from gen
        return

    def wrapper(self: "LitContainerApi", *args: Any, **kwargs: Any) -> Callable:
        try:
            return func(self, *args, **kwargs)
        except LCRAuthFailedError:
            self.authenticate(reauth=True)
            return func(self, *args, **kwargs)

    if inspect.isgeneratorfunction(func):
        return generator_wrapper

    return wrapper


class LitContainerApi:
    def __init__(self) -> None:
        self._client = LightningClient(max_tries=3)

        try:
            self._docker_client = docker.from_env()
            self._docker_client.ping()
            self._docker_auth_config = {}
        except docker.errors.DockerException:
            raise RuntimeError(
                "Failed to connect to Docker, follow these steps to start it: https://docs.docker.com/engine/daemon/start/"
            ) from None

    def authenticate(self, reauth: bool = False) -> bool:
        resp = None
        try:
            authed_user = self._client.auth_service_get_user()
            username = authed_user.username
            api_key = authed_user.api_key
            registry = _get_registry_url()
            resp = self._docker_client.login(username, password=api_key, registry=registry, reauth=reauth)

            if (
                resp.get("username", None) == username
                and resp.get("password", None) == api_key
                and resp.get("serveraddress", None) == registry
            ):
                self._docker_auth_config = {"username": username, "password": api_key}
                return True

            # This is a new 200 response auth attempt from the client.
            if "Status" in resp and resp["Status"] == "Login Succeeded":
                self._docker_auth_config = {"username": username, "password": api_key}
                return True

            return False
        except Exception as e:
            print(f"Authentication error: {e} resp: {resp}")
            return False

    def list_containers(self, project_id: str) -> List:
        project = self._client.lit_registry_service_get_lit_project_registry(project_id)
        return project.repositories

    def delete_container(self, project_id: str, container: str) -> V1DeleteLitRepositoryResponse:
        try:
            return self._client.lit_registry_service_delete_lit_repository(project_id, container)
        except Exception as e:
            raise ValueError(f"Could not delete container {container} from project {project_id}: {e!s}") from e

    @retry_on_lcr_auth_failure
    def upload_container(self, container: str, teamspace: Teamspace, tag: str) -> Generator[dict, None, None]:
        try:
            self._docker_client.images.get(container)
        except docker.errors.ImageNotFound:
            try:
                self._docker_client.images.pull(container, tag)
                self._docker_client.images.get(container)
            except docker.errors.APIError as e:
                raise ValueError(f"Could not pull container {container}") from e
            except docker.errors.ImageNotFound as e:
                raise ValueError(f"Container {container} does not exist") from e
            except Exception as e:
                raise ValueError(f"Unable to upload {container}") from e

        registry_url = _get_registry_url()
        container_basename = container.split("/")[-1]
        repository = f"{registry_url}/lit-container/{teamspace.owner.name}/{teamspace.name}/{container_basename}"
        tagged = self._docker_client.api.tag(container, repository, tag)
        if not tagged:
            raise ValueError(f"Could not tag container {container} with {repository}:{tag}")
        yield from self._push_with_retry(repository)
        yield {
            "finish": True,
            "url": f"{LIGHTNING_CLOUD_URL}/{teamspace.owner.name}/{teamspace.name}/containers/{container_basename}",
            "repository": repository,
        }

    def _push_with_retry(self, repository: str, max_retries: int = 3) -> Iterator[Dict[str, Any]]:
        def is_auth_error(error_msg: str) -> bool:
            auth_errors = ["unauthorized", "authentication required", "unauth"]
            return any(err in error_msg.lower() for err in auth_errors)

        def is_timeout_error(error_msg: str) -> bool:
            timeout_errors = ["proxyconnect tcp", "i/o timeout"]
            return any(err in error_msg.lower() for err in timeout_errors)

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    # This is important, if we don't set reauth here then we just keep using the
                    # same authentication context that we know just failed.
                    self.authenticate(reauth=True)
                    time.sleep(2)

                lines = self._docker_client.api.push(
                    repository, stream=True, decode=True, auth_config=self._docker_auth_config
                )
                for line in lines:
                    if isinstance(line, dict) and "error" in line:
                        error = line["error"]
                        if is_auth_error(error) or is_timeout_error(error):
                            if attempt < max_retries - 1:
                                break
                            raise DockerPushError(f"Max retries reached: {error}")
                        raise DockerPushError(f"Push error: {error}")
                    yield line
                else:
                    return

            except docker.errors.APIError as e:
                if (is_auth_error(str(e)) or is_timeout_error(str(e))) and attempt < max_retries - 1:
                    continue
                raise DockerPushError(f"Push failed: {e}") from e

        raise DockerPushError("Max push retries reached")

    @retry_on_lcr_auth_failure
    def download_container(self, container: str, teamspace: Teamspace, tag: str) -> Generator[str, None, None]:
        registry_url = _get_registry_url()
        repository = f"{registry_url}/lit-container/{teamspace.owner.name}/{teamspace.name}/{container}"
        try:
            self._docker_client.images.pull(repository, tag=tag, auth_config=self._docker_auth_config)
        except requests.exceptions.HTTPError as e:
            if "unauthorized" in e.response.text:
                raise LCRAuthFailedError() from e
        except docker.errors.APIError as e:
            raise ValueError(f"Could not pull container {container} from {repository}:{tag}") from e
        return self._docker_client.api.tag(repository, container, tag)
