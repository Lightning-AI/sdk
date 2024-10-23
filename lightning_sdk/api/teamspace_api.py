import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from lightning_sdk.api.utils import _download_model_files, _DummyBody, _ModelFileUploader
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi import (
    ModelsStoreApi,
    ProjectIdAgentsBody,
    ProjectIdModelsBody,
    V1Assistant,
    V1CloudSpace,
    V1Endpoint,
    V1ModelVersionArchive,
    V1Project,
    V1ProjectClusterBinding,
    V1PromptSuggestion,
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

        if not teamspaces:
            raise ValueError(f"Teamspace {name} does not exist")

        if len(teamspaces) > 1:
            raise RuntimeError(f"{name} is no unique name for a Teamspace")

        return teamspaces[0]

    def _get_teamspace_by_id(self, teamspace_id: str) -> V1Project:
        return self._client.projects_service_get_project(teamspace_id)

    def list_teamspaces(self, owner_id: str, name: Optional[str] = None) -> Optional[V1Project]:
        """Lists teamspaces from owner.

        If name is passed only teamspaces matching that name will be returned

        """
        # cannot list projects the authed user is not a member of
        # -> list projects authed users are members of + filter later on
        res = self._client.projects_service_list_memberships(filter_by_user_id=True)

        teamspaces = []
        for teamspace in res.memberships:
            # if name is provided, filter for teamspaces matching that name
            match_name = name is None or teamspace.name == name or teamspace.display_name == name
            # and only return teamspaces actually owned by the id
            if match_name and teamspace.owner_id == owner_id:
                teamspaces.append(self._get_teamspace_by_id(teamspace.project_id))
        return teamspaces

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
        """Gets the currently logged-in user."""
        auth = Auth()
        auth.authenticate()
        return auth.user_id

    def get_default_cluster_id(self, teamspace_id: str) -> str:
        """Get the default cluster id of the teamspace."""
        return self._client.projects_service_get_project(teamspace_id).project_settings.preferred_cluster

    def _determine_cluster_id(self, teamspace_id: str) -> str:
        """Attempts to determine the cluster id of the teamspace.

        Raises an error if it's ambiguous.

        """
        # when you run  from studio, the cluster is with env. vars
        cluster_id = os.getenv("LIGHTNING_CLUSTER_ID")
        if cluster_id:
            return cluster_id

        # if there is only one cluster, use that and ignore default setting :D
        cluster_ids = [c.cluster_id for c in self.list_clusters(teamspace_id=teamspace_id)]
        if len(cluster_ids) == 1:
            return cluster_ids[0]
        # otherwise, try to determine the default cluster, another API call but we do not care :(
        default_cluster_id = self.get_default_cluster_id(teamspace_id=teamspace_id)
        if default_cluster_id:
            return default_cluster_id
        raise RuntimeError(
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

    def create_model(
        self,
        name: str,
        metadata: Dict[str, str],
        private: bool,
        teamspace_id: str,
        cluster_id: str,
    ) -> V1ModelVersionArchive:
        api = ModelsStoreApi(self._client.api_client)
        body = ProjectIdModelsBody(cluster_id=cluster_id, metadata=metadata, name=name, private=private)
        return api.models_store_create_model(body, project_id=teamspace_id)

    def upload_model_file(
        self,
        model_id: str,
        version: str,
        local_path: Path,
        remote_path: str,
        cluster_id: str,
        teamspace_id: str,
        progress_bar: bool = True,
    ) -> None:
        uploader = _ModelFileUploader(
            client=self._client,
            model_id=model_id,
            version=version,
            teamspace_id=teamspace_id,
            cluster_id=cluster_id,
            file_path=str(local_path),
            remote_path=str(remote_path),
            progress_bar=progress_bar,
        )
        uploader()

    def upload_model_files(
        self,
        model_id: str,
        version: str,
        root_path: Path,
        filepaths: List[Path],
        cluster_id: str,
        teamspace_id: str,
        progress_bar: bool = True,
    ) -> None:
        for filepath in filepaths:
            self.upload_model_file(
                model_id=model_id,
                version=version,
                local_path=filepath,
                remote_path=str(filepath.relative_to(root_path)),
                cluster_id=cluster_id,
                teamspace_id=teamspace_id,
                progress_bar=progress_bar,  # TODO: Global progress bar
            )

    def complete_model_upload(self, model_id: str, version: str, teamspace_id: str) -> None:
        api = ModelsStoreApi(self._client.api_client)
        api.models_store_complete_model_upload(
            body=_DummyBody(),
            project_id=teamspace_id,
            model_id=model_id,
            version=version,
        )

    def download_model_files(
        self,
        name: str,
        version: str,
        download_dir: Path,
        teamspace_id: str,
        progress_bar: bool = True,
    ) -> List[str]:
        return _download_model_files(
            client=self._client,
            teamspace_id=teamspace_id,
            name=name,
            version=version,
            download_dir=download_dir,
            progress_bar=progress_bar,
        )


@dataclass
class UploadedModelInfo:
    name: str
    version: str
    teamspace: str
    cluster: str
