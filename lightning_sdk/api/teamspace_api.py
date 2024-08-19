import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from lightning_sdk.api.utils import _FileUploader
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi import (
    ModelsStoreApi,
    ProjectIdAgentsBody,
    V1Assistant,
    V1CloudSpace,
    V1Endpoint,
    V1Project,
    V1ProjectClusterBinding,
    V1PromptSuggestion,
    V1UploadModelRequest,
    V1UpstreamOpenAI,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient

__all__ = ["TeamspaceApi"]


class TeamspaceApi:
    """Internal API client for Teamspace requests (mainly http requests)."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)

    def get_teamspace(self, name: str, owner_id: str) -> V1Project:
        """Get the current teamspace from the owner."""
        teamspaces = self.list_teamspaces(name=name, owner_id=owner_id)

        if len(teamspaces) == 0:
            raise ValueError(f"Teamspace {name} does not exist")

        if len(teamspaces) > 1:
            raise RuntimeError(f"{name} is no unique name for a Teamspace")

        return teamspaces[0]

    def _get_teamspace_by_id(self, teamspace_id: str) -> V1Project:
        return self._client.projects_service_get_project(teamspace_id)

    def list_teamspaces(self, owner_id: str, name: Optional[str]) -> Optional[V1Project]:
        """Lists teamspaces from owner.

        If name is passed only teamspaces matching that name will be returned

        """
        # cannot list projects the authed user is not a member of
        # -> list projects authed users are members of + filter later on
        res = self._client.projects_service_list_memberships(filter_by_user_id=True)

        return [
            self._get_teamspace_by_id(m.project_id)
            for m in filter(
                # only return teamspaces actually owned by the id
                lambda x: x.owner_id == owner_id,
                # if name is provided, filter for teamspaces matching that name
                filter(lambda x: name is None or x.name == name or x.display_name == name, res.memberships),
            )
        ]

    def list_studios(self, teamspace_id: str, cluster_id: str = "") -> List[V1CloudSpace]:
        """List studios in teamspace."""
        kwargs = {"project_id": teamspace_id, "user_id": self._get_authed_user_id()}

        if cluster_id:
            kwargs["cluster_id"] = cluster_id

        cloudspaces = []

        while True:
            resp = self._client.cloud_space_service_list_cloud_spaces(**kwargs)

            cloudspaces.extend(resp.cloudspaces)

            if not resp.next_page_token:
                break

            kwargs["page_token"] = resp.next_page_token

        return cloudspaces

    def list_clusters(self, teamspace_id: str) -> List[V1ProjectClusterBinding]:
        """Lists clusters in a teamspace."""
        return self._client.projects_service_list_project_cluster_bindings(project_id=teamspace_id).clusters

    def _get_authed_user_id(self) -> str:
        """Gets the currently logged in user."""
        auth = Auth()
        auth.authenticate()
        return auth.user_id

    def _try_get_cluster_id(self, teamspace_id: str) -> str:
        """Attempts to determine the cluster id of the teamspace.

        Raises an error if it's ambiguous.

        """
        cluster_id = os.getenv("LIGHTNING_CLUSTER_ID")
        if cluster_id:
            return cluster_id
        cluster_ids = [c.cluster_id for c in self.list_clusters(teamspace_id=teamspace_id)]
        if len(cluster_ids) == 1:
            return cluster_ids[0]
        raise ValueError(
            "Could not determine the current cluster id. Please provide it manually as input."
            f" Choices are: {', '.join(cluster_ids)}"
        )

    def create_agent(
        self,
        name: str,
        teamspace_id: str,
        api_key: str,
        base_url: str,
        model: str,
        org_id: Optional[str] = "",
        prompt_template: Optional[str] = "",
        description: Optional[str] = "",
        prompt_suggestions: Optional[List[str]] = None,
        file_uploads_enabled: Optional[bool] = None,
    ) -> V1Assistant:
        openai_endpoint = V1UpstreamOpenAI(api_key=api_key, base_url=base_url)

        endpoint = V1Endpoint(
            name=name,
            openai=openai_endpoint,
            project_id=teamspace_id,
        )

        ([V1PromptSuggestion(content=suggestion) for suggestion in prompt_suggestions] if prompt_suggestions else None)

        body = ProjectIdAgentsBody(
            endpoint=endpoint,
            name=name,
            model=model,
            org_id=org_id,
            prompt_template=prompt_template,
            description=description,
            file_uploads_enabled=file_uploads_enabled,
        )

        return self._client.assistants_service_create_assistant(body=body, project_id=teamspace_id)

    def request_artifact_upload(
        self,
        name: str,
        metadata: Dict[str, str],
        private: bool,
        teamspace_id: str,
        cluster_id: str,
        version: Optional[str] = None,
    ) -> Tuple[str, str]:
        api = ModelsStoreApi(self._client.api_client)
        body = V1UploadModelRequest(
            metadata=metadata,
            name=name,
            private=private,
            project_id=teamspace_id,
            cluster_id=cluster_id,
            version=version,
        )
        response = api.models_store_upload_model(body)
        return response.upload_dir, response.cluster_id

    def upload_artifact_file(
        self,
        local_file_path: Path,
        remote_dir: str,
        cluster_id: str,
        teamspace_id: str,
        progress_bar: bool = True,
    ) -> None:
        remote_path = Path(remote_dir, local_file_path.name)
        # Strip away the first two parts 'projects/project_id/' because uploader expects path
        # relative to project folder
        remote_path = Path("/", *remote_path.parts[2:])

        uploader = _FileUploader(
            client=self._client,
            teamspace_id=teamspace_id,
            cluster_id=cluster_id,
            file_path=str(local_file_path),
            remote_path=str(remote_path),
            progress_bar=progress_bar,
        )
        uploader()

    def request_artifact_download(self, name: str, version: str) -> Tuple[str, str]:
        api = ModelsStoreApi(self._client.api_client)
        response = api.models_store_download_model(name=name, version=version)
        # TODO: Support downloading multiple files
        filename = response.metadata["filenames"].split(",")[0]
        download_url = response.download_url
        return filename, download_url

    def download_artifact_file(self, url: str, download_path: Path) -> None:
        response = requests.get(url, stream=True)
        with open(download_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=(4096 * 8)):
                file.write(chunk)
