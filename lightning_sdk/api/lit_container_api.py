import inspect
import time
from typing import Any, Callable, Dict, Generator, Iterator, List, Optional

import docker
import requests
from rich.console import Console

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


class DockerNotRunningError(Exception):
    def __init__(self, message: str = "Failed to connect to Docker") -> None:
        self.message = message
        super().__init__(self.message)

    def print_help(self) -> None:
        console = Console()
        console.print("[bold red]Docker Error: Failed to connect to Docker. Is it running?[/bold red]")
        console.print("[yellow]Troubleshooting:[/yellow]")
        console.print("1. Check if Docker daemon is running")
        console.print("2. Verify your user has proper permissions")
        console.print("3. Try restarting Docker service")
        console.print("4. Read more here: https://docs.docker.com/engine/daemon/start/")


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
            raise DockerNotRunningError() from None

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

    def list_containers(self, project_id: str, cloud_account: Optional[str] = None) -> List:
        """Lists containers of the project ID.

        :param project_id: The non-human readable project ID used internally to identify projects.
        :param cloud_account: The cluster ID of the cloud account. If None, will use the default cluster.
        :return:
        """
        if cloud_account is None:
            project = self._client.lit_registry_service_get_lit_project_registry(project_id)
        else:
            project = self._client.lit_registry_service_get_lit_project_registry(project_id, cluster_id=cloud_account)

        return project.repositories

    def delete_container(self, project_id: str, container: str) -> V1DeleteLitRepositoryResponse:
        """Deletes the container from LitCR. Garbage collection will come in and do the final sweep of the blob.

        :param project_id: The non-human readable project ID used internally to identify projects.
        :param container: The name of the docker container a user wants to push up, ie, nginx, vllm, etc
        :return:
        """
        try:
            return self._client.lit_registry_service_delete_lit_repository(project_id, container)
        except Exception as e:
            raise ValueError(f"Could not delete container {container} from project {project_id}: {e!s}") from e

    def get_container_url(
        self, repository: str, tag: str, teamspace: Teamspace, cloud_account: Optional[str] = None
    ) -> str:
        """Docker container will be pushed to the URL returned from this function."""
        registry_url = _get_registry_url()
        container_basename = repository.split("/")[-1]
        return (
            f"{registry_url}/lit-container{f'-{cloud_account}' if cloud_account is not None else ''}/"
            f"{teamspace.owner.name}/{teamspace.name}/{container_basename}"
        )

    @retry_on_lcr_auth_failure
    def upload_container(
        self,
        container: str,
        teamspace: Teamspace,
        tag: str,
        cloud_account: str,
        platform: str,
        return_final_dict: bool = False,
    ) -> Generator[dict, None, Dict]:
        """Upload container will push the container to LitCR.

        It uses docker push API to interact with docker daemon which will then push the container to a storage
        location defined by teamspace + cloud_account. Will retry pushes if not authenticated or if push errors happen

        :param container: The name of the docker container a user wants to push up, ie, nginx, vllm, etc
        :param teamspace: The teamspace he container is going to appear in. This is <OWNER_ID>/<TEAMSPACE_NAME>
        :param tag: The container tag, default will latest.
        :param cloud_account: If empty will be pushed to Lightning SaaS storage. Otherwise, this will be cluster_id.
            Named cloud-account in the CLI options.
        :param platform: If empty will be linux/amd64. This is important because our entire deployment infra runs on
            linux/amd64. Will show user a warning otherwise.
        :return: Generator[dict, None, dict]
        """
        try:
            self._docker_client.images.get(f"{container}:{tag}")
        except docker.errors.ImageNotFound:
            try:
                self._docker_client.images.pull(repository=container, tag=tag, platform=platform)
                self._docker_client.images.get(f"{container}:{tag}")
            except docker.errors.ImageNotFound as e:
                raise ValueError(f"Container {container}:{tag} does not exist") from e
            except docker.errors.APIError as e:
                raise ValueError(f"Could not pull container {container}") from e
            except Exception as e:
                raise ValueError(f"Unable to upload {container}:{tag}") from e

        repository = self.get_container_url(container, tag, teamspace, cloud_account)
        tagged = self._docker_client.api.tag(f"{container}:{tag}", repository, tag)
        if not tagged:
            raise ValueError(f"Could not tag container {container}:{tag} with {repository}:{tag}")
        yield from self._push_with_retry(repository, tag=tag)

        if return_final_dict:
            container_basename = repository.split("/")[-1]
            yield {
                "finish": True,
                "url": f"{LIGHTNING_CLOUD_URL}/{teamspace.owner.name}/{teamspace.name}/containers/"
                f"{container_basename}?section=tags"
                f"{f'?clusterId={cloud_account}' if cloud_account is not None else ''}",
                "repository": repository,
            }

    def _push_with_retry(self, repository: str, tag: str, max_retries: int = 3) -> Iterator[Dict[str, Any]]:
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
                    repository, tag=tag, stream=True, decode=True, auth_config=self._docker_auth_config
                )
                for line in lines:
                    if isinstance(line, dict) and "error" in line:
                        error = line["error"]
                        if is_auth_error(error) or is_timeout_error(error):
                            if attempt < max_retries - 1:
                                break
                            raise DockerPushError(f"Max retries reached while pushing: {error}")
                        raise DockerPushError(f"Push error: {error}")
                    yield line
                else:
                    return

            except docker.errors.APIError as e:
                if (is_auth_error(str(e)) or is_timeout_error(str(e))) and attempt < max_retries - 1:
                    continue
                raise DockerPushError("Pushing the container failed") from e

        raise DockerPushError("Max push retries reached")

    @retry_on_lcr_auth_failure
    def download_container(
        self, container: str, teamspace: Teamspace, tag: str, cloud_account: Optional[str] = None
    ) -> Generator[str, None, None]:
        """Will download container from LitCR. Optionally from a BYOC cluster.

        :param container: The name of the container to download
        :param teamspace: The teamspace containing the container
        :param tag: The tag of the container to download
        :return: Generator yielding download status
        """
        registry_url = _get_registry_url()
        repository = (
            f"{registry_url}/lit-container{f'-{cloud_account}' if cloud_account is not None else ''}/"
            f"{teamspace.owner.name}/{teamspace.name}/{container}"
        )
        try:
            self._docker_client.images.pull(repository, tag=tag, auth_config=self._docker_auth_config)
        except requests.exceptions.HTTPError as e:
            if "unauthorized" in e.response.text:
                raise LCRAuthFailedError() from e
        except docker.errors.APIError as e:
            raise ValueError(f"Could not pull container {container} from {repository}:{tag}") from e
        return self._docker_client.api.tag(repository, container, tag)
