from datetime import datetime
from typing import Dict, List, Optional

from rich.console import Console

from lightning_sdk.api.lit_container_api import LitContainerApi
from lightning_sdk.utils.resolve import _resolve_teamspace


class LitContainer:
    def __init__(self) -> None:
        self._api = LitContainerApi()

    def list_containers(
        self, teamspace: str, org: Optional[str] = None, user: Optional[str] = None, cloud_account: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """List available docker repositories.

        Args:
            teamspace: The teamspace to list containers from.
            org: The organization to list containers from.
            user: The user to list the containers from.
            cloud_account: The cloud account to list the containers from.

        Returns:
            A list of dictionaries containing repository details.
        """
        console = Console()
        try:
            teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
        except Exception:
            console.print(f"[bold red]Could not resolve teamspace: {teamspace}[/bold red]")
            return []
        project_id = teamspace.id
        repositories = self._api.list_containers(project_id, cloud_account=cloud_account)
        table = []
        for repo in repositories:
            created_date = repo.creation_time
            if isinstance(repo.creation_time, str):
                created_date = datetime.fromisoformat(created_date)

            created = created_date.strftime("%Y-%m-%d %H:%M:%S")

            table.append(
                {
                    "REPOSITORY": repo.name,
                    "CLOUD ACCOUNT": cloud_account
                    if cloud_account != "" and cloud_account is not None
                    else "Lightning cloud",
                    "CREATED": created,
                    "LATEST TAG": repo.latest_artifact.tag_name,
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
        self,
        container: str,
        teamspace: str,
        org: Optional[str] = None,
        user: Optional[str] = None,
        tag: str = "latest",
        cloud_account: Optional[str] = None,
        platform: Optional[str] = "linux/amd64",
        return_final_dict: bool = False,
    ) -> Optional[Dict]:
        """Upload a container to the docker registry.

        Args:
            container: The name of the container to upload.
            teamspace: The teamspace which contains the container.
            org: The organization which contains the container.
            user: The user which contains the container.
            tag: The tag to use for the container.
            cloud_account: The cloud account where the container is stored.
            platform: The platform the container is meant to run on.
            return_final_dict: Instructs function to return metadata about container location in platform.
        """
        try:
            teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
        except Exception as e:
            raise ValueError(f"Could not resolve teamspace: {e}") from e

        resp = self._api.upload_container(
            container, teamspace, tag, cloud_account, platform=platform, return_final_dict=return_final_dict
        )

        final_dict = None
        for line in resp:
            print(line)
            if return_final_dict and isinstance(line, dict) and line.get("finish") is True:
                final_dict = line

        return final_dict if return_final_dict else None

    def download_container(
        self,
        container: str,
        teamspace: str,
        org: Optional[str] = None,
        user: Optional[str] = None,
        tag: str = "latest",
        cloud_account: Optional[str] = None,
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

        return self._api.download_container(container, teamspace, tag, cloud_account)
