from datetime import datetime
from typing import Dict, List, Optional

from lightning_sdk.api.lit_container_api import LitContainerApi
from lightning_sdk.utils.resolve import _resolve_teamspace


class LitContainer:
    def __init__(self) -> None:
        self._api = LitContainerApi()

    def list_containers(
        self, teamspace: str, org: Optional[str] = None, user: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """List available docker repositories.

        Args:
            teamspace: The teamspace to list containers from.
            org: The organization to list containers from.
            user: The user to list the containers from.

        Returns:
            A list of dictionaries containing repository details.
        """
        try:
            teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
        except Exception as e:
            raise ValueError(f"Could not resolve teamspace: {e}") from e
        project_id = teamspace.id
        repositories = self._api.list_containers(project_id)
        table = []
        for repo in repositories:
            created_date = repo.creation_time
            if isinstance(repo.creation_time, str):
                created_date = datetime.fromisoformat(created_date)

            created = created_date.strftime("%Y-%m-%d %H:%M:%S")

            table.append(
                {
                    "REPOSITORY": repo.name,
                    "IMAGE ID": repo.id,
                    "CREATED": created,
                }
            )
        return table

    def delete_container(
        self, container: str, teamspace: str, org: Optional[str] = None, user: Optional[str] = None
    ) -> None:
        """Delete a docker container.

        Args:
            container: Name of the container to delete.
            teamspace: The teamspace which contains the container.
            org: The organization which contains the container.
            user: The user which contains the container.
        """
        try:
            teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
        except Exception as e:
            raise ValueError("Could not resolve teamspace") from e
        project_id = teamspace.id
        return self._api.delete_container(project_id, container)

    def upload_container(
        self, container: str, teamspace: str, org: Optional[str] = None, user: Optional[str] = None, tag: str = "latest"
    ) -> None:
        """Upload a container to the docker registry.

        Args:
            container: The name of the container to upload.
            teamspace: The teamspace which contains the container.
            org: The organization which contains the container.
            user: The user which contains the container.
            tag: The tag to use for the container.
        """
        try:
            teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
        except Exception as e:
            raise ValueError(f"Could not resolve teamspace: {e}") from e

        resp = self._api.upload_container(container, teamspace, tag)
        for line in resp:
            print(line)

    def download_container(
        self, container: str, teamspace: str, org: Optional[str] = None, user: Optional[str] = None, tag: str = "latest"
    ) -> None:
        """Download a container from the docker registry.

        Args:
            container: The name of the container to download.
            teamspace: The teamspace which contains the container.
            org: The organization which contains the container.
            user: The user which contains the container.
            tag: The tag to use for the container.
        """
        try:
            teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
        except Exception as e:
            raise ValueError(f"Could not resolve teamspace: {e}") from e

        return self._api.download_container(container, teamspace, tag)
