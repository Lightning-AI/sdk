import concurrent
import os
import re
import warnings
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union

import requests
from tqdm.auto import tqdm

from lightning_sdk.api.utils import (
    Experiment,
    _authenticate_and_get_token,
    _BlobUploader,
    _download_model_files,
    _DummyBody,
    _get_model_version,
    _ModelFileUploader,
)
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi import (
    AssistantsServiceCreateAssistantBody,
    DataConnectionServiceCreateDataConnectionBody,
    ModelsStoreCreateModelBody,
    ModelsStoreCreateModelVersionBody,
    SecretServiceCreateSecretBody,
    SecretServiceUpdateSecretBody,
    V1Assistant,
    V1CloudSpace,
    V1ClusterAccelerator,
    V1EfsConfig,
    V1Endpoint,
    V1ExternalCluster,
    V1GCSFolderDataConnection,
    V1Job,
    V1Model,
    V1ModelVersionArchive,
    V1MultiMachineJob,
    V1Project,
    V1ProjectClusterBinding,
    V1PromptSuggestion,
    V1R2DataConnection,
    V1S3FolderDataConnection,
    V1Secret,
    V1SecretType,
    V1UpstreamOpenAI,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.machine import Machine

__all__ = ["SecretType", "TeamspaceApi"]


class SecretType(Enum):
    """Type of an encrypted secret.

    ``GENERIC`` secrets are exposed as environment variables. ``HF_TOKEN`` tags a
    secret as a HuggingFace access token so it can be referenced when deploying
    gated or private HuggingFace models (``Deployment.start(hf_token_secret=...)``).
    """

    GENERIC = "generic"
    HF_TOKEN = "hf_token"

    def __str__(self) -> str:
        """Converts the SecretType to a str.

        Returns:
            str: The string value of the enum member (e.g. ``"hf_token"``).
        """
        return self.value


_SECRET_TYPE_TO_API = {
    SecretType.GENERIC: V1SecretType.UNSPECIFIED,
    SecretType.HF_TOKEN: V1SecretType.HF_TOKEN,
}


def _resolve_secret_type(secret_type: Union[str, SecretType]) -> V1SecretType:
    """Resolve a user-provided secret type (enum or string) to a ``V1SecretType``.

    Args:
        secret_type: A ``SecretType`` member or its string value (e.g. ``"hf_token"``).

    Raises:
        ValueError: If ``secret_type`` is not a valid secret type.
    """
    try:
        resolved = SecretType(secret_type)
    except ValueError:
        valid = ", ".join(repr(member.value) for member in SecretType)
        raise ValueError(f"Invalid secret_type {secret_type!r}. Must be one of: {valid}.") from None
    return _SECRET_TYPE_TO_API[resolved]


class TeamspaceApi:
    """Internal API client for Teamspace requests (mainly http requests)."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)

    def get_teamspace(self, name: str, owner_id: str) -> V1Project:
        """Get the current teamspace from the owner.

        Args:
            name: Name of the teamspace to look up.
            owner_id: User or organization ID that owns the teamspace.

        Returns:
            The matching ``V1Project`` object.

        Raises:
            ValueError: If no teamspace with the given name exists for the owner.
            RuntimeError: If the name matches more than one teamspace.
        """
        teamspaces = self.list_teamspaces(name=name, owner_id=owner_id)

        if not teamspaces:
            raise ValueError(f"Teamspace {name} does not exist")

        if len(teamspaces) > 1:
            raise RuntimeError(f"{name} is no unique name for a Teamspace")

        return teamspaces[0]

    def _get_teamspace_by_id(self, teamspace_id: str) -> V1Project:
        """Fetch a teamspace by its unique ID.

        Args:
            teamspace_id: Unique ID of the teamspace to fetch.

        Returns:
            The matching ``V1Project`` object.
        """
        return self._client.projects_service_get_project(teamspace_id)

    def list_teamspaces(self, owner_id: str, name: Optional[str] = None) -> Optional[List[V1Project]]:
        """Lists teamspaces from owner.

        If name is passed only teamspaces matching that name will be returned.

        Args:
            owner_id: User or organization ID whose teamspaces to list.
            name: If provided, only teamspaces matching this name are returned.

        Returns:
            List of ``V1Project`` objects owned by the given owner, optionally filtered by name.
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

    def list_studios(self, teamspace_id: str, cloud_account: str = "") -> List[V1CloudSpace]:
        """List studios in teamspace.

        Args:
            teamspace_id: ID of the teamspace to list studios in.
            cloud_account: Optional cloud account ID to filter studios by cluster.

        Returns:
            List of ``V1CloudSpace`` objects in the teamspace.
        """
        kwargs = {"project_id": teamspace_id, "user_id": self._get_authed_user_id()}

        if cloud_account:
            kwargs["cluster_id"] = cloud_account

        cloudspaces = []

        while True:
            resp = self._client.cloud_space_service_list_cloud_spaces(**kwargs)

            cloudspaces.extend(resp.cloudspaces)

            if not resp.next_page_token:
                break

            kwargs["page_token"] = resp.next_page_token

        return cloudspaces

    def list_cloud_accounts(self, teamspace_id: str) -> List[V1ProjectClusterBinding]:
        """Lists cloud_accounts in a teamspace.

        Args:
            teamspace_id: ID of the teamspace to list cloud accounts for.

        Returns:
            List of ``V1ProjectClusterBinding`` objects representing the cloud accounts.
        """
        return self._client.projects_service_list_project_cluster_bindings(project_id=teamspace_id).clusters

    def _get_authed_user_id(self) -> str:
        """Gets the currently logged-in user.

        Returns:
            User ID string of the currently authenticated user.
        """
        auth = Auth()
        auth.authenticate()
        return auth.user_id

    def get_default_cloud_account(self, teamspace_id: str) -> str:
        """Get the default cloud account id of the teamspace.

        Args:
            teamspace_id: ID of the teamspace to query.

        Returns:
            The preferred cluster (cloud account) ID string for the teamspace.
        """
        return self._client.projects_service_get_project(teamspace_id).project_settings.preferred_cluster

    def _determine_cloud_account(self, teamspace_id: str) -> str:
        """Attempts to determine the cloud account id of the teamspace.

        Raises an error if it's ambiguous.

        Args:
            teamspace_id: ID of the teamspace to determine the cloud account for.

        Returns:
            The resolved cloud account ID string.

        Raises:
            RuntimeError: If the cloud account cannot be determined unambiguously.
        """
        # when you run  from studio, the cloud account is with env. vars
        cloud_account = os.getenv("LIGHTNING_CLUSTER_ID")
        if cloud_account:
            return cloud_account

        # if there is only one cluster, use that and ignore default setting :D
        cloud_accounts = [c.cluster_id for c in self.list_cloud_accounts(teamspace_id=teamspace_id)]
        if len(cloud_accounts) == 1:
            return cloud_accounts[0]
        # otherwise, try to determine the default cloud_account, another API call but we do not care :(
        default_cloud_account = self.get_default_cloud_account(teamspace_id=teamspace_id)
        if default_cloud_account:
            return default_cloud_account
        raise RuntimeError(
            "Could not determine the current cloud account. Please provide it manually as input."
            f" Choices are: {', '.join(cloud_accounts)}"
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
        """Create a new AI assistant agent backed by an OpenAI-compatible endpoint.

        Args:
            name: Display name for the agent.
            teamspace_id: ID of the teamspace to create the agent in.
            api_key: API key for the upstream OpenAI-compatible endpoint.
            base_url: Base URL of the upstream endpoint.
            model: Model identifier to use for the agent.
            org_id: Optional organization ID to scope the agent to.
            prompt_template: Optional system prompt template.
            description: Optional human-readable description of the agent.
            prompt_suggestions: Optional list of suggested prompts shown to users.
            file_uploads_enabled: Whether to allow file uploads in the agent chat.

        Returns:
            The created ``V1Assistant`` object.
        """
        openai_endpoint = V1UpstreamOpenAI(api_key=api_key, base_url=base_url)

        endpoint = V1Endpoint(
            name=name,
            openai=openai_endpoint,
            project_id=teamspace_id,
        )

        ([V1PromptSuggestion(content=suggestion) for suggestion in prompt_suggestions] if prompt_suggestions else None)

        body = AssistantsServiceCreateAssistantBody(
            endpoint=endpoint,
            name=name,
            model=model,
            org_id=org_id,
            prompt_template=prompt_template,
            description=description,
            file_uploads_enabled=file_uploads_enabled,
        )

        return self._client.assistants_service_create_assistant(body=body, project_id=teamspace_id)

    def get_model_version(self, name: str, version: Optional[str], teamspace_id: str) -> V1ModelVersionArchive:
        """Fetch a specific model version archive by model name and optional version tag.

        Args:
            name: Model name to look up.
            version: Version tag to fetch; uses the default version if ``None``.
            teamspace_id: ID of the teamspace owning the model.

        Returns:
            The matching ``V1ModelVersionArchive`` object.
        """
        return _get_model_version(client=self._client, name=name, version=version, teamspace_id=teamspace_id)

    def create_model(
        self,
        name: str,
        version: Optional[str],
        metadata: Dict[str, str],
        private: bool,
        teamspace_id: str,
        cloud_account: str,
        experiment: Optional[Experiment] = None,
    ) -> V1ModelVersionArchive:
        """Create a new model or add a version to an existing model with the same name.

        Args:
            name: Model name.
            version: Explicit version tag; the server assigns one if ``None``.
            metadata: Arbitrary key-value metadata to attach to the model.
            private: Whether the model should be private.
            teamspace_id: ID of the teamspace to create the model in.
            cloud_account: Cloud account ID for storing model artifacts.
            experiment: Optional experiment to associate with this model version.

        Returns:
            The created ``V1ModelVersionArchive``.
        """
        # ask if such model already exists by listing models with specific name
        models = self._client.models_store_list_models(project_id=teamspace_id, name=name).models
        experiment_id = experiment.id if experiment is not None else None
        if len(models) == 0:
            return self._client.models_store_create_model(
                body=ModelsStoreCreateModelBody(
                    cluster_id=cloud_account,
                    metadata=metadata,
                    name=name,
                    private=private,
                    metrics_stream_id=experiment_id,
                ),
                project_id=teamspace_id,
            )
        assert len(models) == 1, "Multiple models with the same name found"
        return self._client.models_store_create_model_version(
            body=ModelsStoreCreateModelVersionBody(
                cluster_id=cloud_account,
                version=version,
                metrics_stream_id=experiment_id,
            ),
            project_id=teamspace_id,
            model_id=models[0].id,
        )

    def delete_model(self, name: str, version: Optional[str], teamspace_id: str) -> None:
        """Delete a model or a version from the model store.

        Args:
            name: Model name to delete.
            version: Version tag to delete; deletes the entire model if ``None``.
            teamspace_id: ID of the teamspace owning the model.
        """
        model = self.get_model(teamspace_id=teamspace_id, model_name=name)
        # decide if delete only version of whole model
        if version:
            if version == "default":
                version = model.default_version
            self._client.models_store_delete_model_version(project_id=teamspace_id, model_id=model.id, version=version)
        else:
            self._client.models_store_delete_model(project_id=teamspace_id, model_id=model.id)

    def upload_model_file(
        self,
        model_id: str,
        version: str,
        local_path: Path,
        remote_path: str,
        teamspace_id: str,
        progress_bar: bool = True,
    ) -> None:
        """Upload a file to the model store.

        Args:
            model_id: Unique ID of the model to upload the file to.
            version: Version tag of the model version to attach the file to.
            local_path: Local filesystem path of the file to upload.
            remote_path: Destination path within the model version artifact store.
            teamspace_id: ID of the teamspace owning the model.
            progress_bar: Whether to display a progress bar during upload.
        """
        uploader = _ModelFileUploader(
            client=self._client,
            model_id=model_id,
            version=version,
            teamspace_id=teamspace_id,
            file_path=str(local_path),
            remote_path=str(remote_path),
            progress_bar=progress_bar,
        )
        uploader()

    def upload_model_files(
        self,
        model_id: str,
        version: str,
        file_paths: List[Path],
        remote_paths: List[str],
        teamspace_id: str,
        progress_bar: bool = True,
    ) -> None:
        """Upload files to the model store.

        Args:
            model_id: Unique ID of the model to upload files to.
            version: Version tag of the model version to attach the files to.
            file_paths: List of local filesystem paths of the files to upload.
            remote_paths: List of destination paths within the model version artifact store;
                must be the same length as ``file_paths``.
            teamspace_id: ID of the teamspace owning the model.
            progress_bar: Whether to display a progress bar during upload.
        """
        main_pbar = tqdm(total=len(file_paths), desc="Uploading files...", position=0) if progress_bar else None
        assert len(file_paths) == len(remote_paths), "File paths and remote paths must have the same length"
        for filepath, remote_path in zip(file_paths, remote_paths):
            self.upload_model_file(
                model_id=model_id,
                version=version,
                local_path=filepath,
                remote_path=remote_path,
                teamspace_id=teamspace_id,
                progress_bar=progress_bar,  # TODO: Global progress bar
            )
            if main_pbar:
                main_pbar.update(1)

    def _complete_model_upload(self, model_id: str, version: str, teamspace_id: str) -> None:
        """Signal to the server that all files for a model version have been uploaded.

        Args:
            model_id: Unique ID of the model whose upload is being completed.
            version: Version tag of the model version being completed.
            teamspace_id: ID of the teamspace owning the model.
        """
        self._client.models_store_complete_model_upload(
            body=_DummyBody(),
            project_id=teamspace_id,
            model_id=model_id,
            version=version,
        )

    def download_model_files(
        self,
        name: str,
        version: Optional[str],
        download_dir: Path,
        teamspace_name: str,
        teamspace_owner_name: str,
        progress_bar: bool = True,
    ) -> List[str]:
        """Download all files for a model version to a local directory.

        Args:
            name: Model name.
            version: Version tag to download; defaults to ``"default"`` if ``None``.
            download_dir: Local directory to write files into.
            teamspace_name: Name of the teamspace owning the model.
            teamspace_owner_name: Username or org name that owns the teamspace.
            progress_bar: Whether to display a progress bar. Defaults to ``True``.

        Returns:
            List of local file paths that were downloaded.
        """
        if version is None:
            version = "default"
        return _download_model_files(
            client=self._client,
            teamspace_name=teamspace_name,
            teamspace_owner_name=teamspace_owner_name,
            name=name,
            version=version,
            download_dir=download_dir,
            progress_bar=progress_bar,
        )

    def list_jobs(self, teamspace_id: str) -> List[V1Job]:
        """Return all v2 jobs in the teamspace.

        Args:
            teamspace_id: ID of the teamspace to list jobs in.

        Returns:
            List of ``V1Job`` objects.
        """
        return self._client.jobs_service_list_jobs(project_id=teamspace_id, standalone=True).jobs

    def list_mmts(self, teamspace_id: str) -> List[V1MultiMachineJob]:
        """Return all v2 multi-machine training jobs.

        Args:
            teamspace_id: ID of the teamspace to list multi-machine jobs in.

        Returns:
            List of ``V1MultiMachineJob`` objects.
        """
        return self._client.jobs_service_list_multi_machine_jobs(project_id=teamspace_id).multi_machine_jobs

    def list_machines(
        self,
        teamspace_id: str,
        cloud_accounts: List[str],
        machine: Optional[Machine] = None,
        org_id: Optional[str] = None,
    ) -> List[V1ClusterAccelerator]:
        """List available accelerators across the given cloud accounts, optionally filtered by machine type.

        Args:
            teamspace_id: ID of the teamspace.
            cloud_accounts: Cloud account IDs to query.
            machine: If provided, only return accelerators matching this machine spec.
            org_id: Organization ID required for non-global cluster accelerator lookups.

        Returns:
            List of matching ``V1ClusterAccelerator`` objects.
        """
        from lightning_sdk.api.cloud_account_api import CloudAccountApi

        cloud_account_api = CloudAccountApi()
        matched_accelerators = []
        for ca in cloud_accounts:
            try:
                accelerators = cloud_account_api.list_cloud_account_accelerators(
                    teamspace_id=teamspace_id,
                    cloud_account_id=ca,
                    org_id=org_id,
                )
                if not accelerators.accelerator:
                    continue

                if accelerators.accelerator:
                    for cluster_machine in accelerators.accelerator:
                        if not machine:
                            matched_accelerators.append(cluster_machine)
                            continue
                        if (
                            cluster_machine.resources.gpu == machine.accelerator_count
                            or cluster_machine.resources.cpu == machine.accelerator_count
                        ) and any(
                            machine.family.lower() in s
                            for s in (
                                cluster_machine.slug,
                                cluster_machine.slug_multi_cloud,
                                cluster_machine.instance_id,
                            )
                        ):
                            matched_accelerators.append(cluster_machine)
            except Exception:
                pass
        return matched_accelerators

    def get_model(self, teamspace_id: str, model_id: Optional[str] = None, model_name: Optional[str] = None) -> V1Model:
        """Fetch a model by ID or by name; exactly one must be provided.

        Args:
            teamspace_id: ID of the teamspace.
            model_id: Unique model ID; takes priority over ``model_name``.
            model_name: Model name; used when ``model_id`` is not given.

        Returns:
            The matching ``V1Model`` object.

        Raises:
            ValueError: If neither argument is provided, or no model with that name exists.
            RuntimeError: If the name matches more than one model.
        """
        if model_id:
            return self._client.models_store_get_model(project_id=teamspace_id, model_id=model_id)
        if not model_name:
            raise ValueError("Either `model_id` or `model_name` must be provided.")
        # list models with specific name
        models = self._client.models_store_list_models(project_id=teamspace_id, name=model_name).models
        if len(models) == 0:
            raise ValueError(f"Model '{model_name}' does not exist.")
        if len(models) > 1:
            raise RuntimeError(f"Model name '{model_name}' is not a unique with this teamspace.")
        # if there is only one model with the name, return it
        return models[0]

    def list_models(self, teamspace_id: str) -> List[V1Model]:
        """Return all models registered in the teamspace.

        Args:
            teamspace_id: ID of the teamspace to list models in.

        Returns:
            List of ``V1Model`` objects registered in the teamspace.
        """
        response = self._client.models_store_list_models(project_id=teamspace_id)
        return response.models

    def list_model_versions(
        self, teamspace_id: str, model_id: Optional[str] = None, model_name: Optional[str] = None
    ) -> List[V1ModelVersionArchive]:
        """List all versions for a model, resolved by ID or by name.

        Args:
            teamspace_id: ID of the teamspace.
            model_id: Unique model ID; resolved from ``model_name`` if not provided.
            model_name: Model name; used to resolve ``model_id`` when not given directly.

        Returns:
            List of ``V1ModelVersionArchive`` objects.
        """
        if model_name and not model_id:
            model_id = self.get_model(teamspace_id=teamspace_id, model_name=model_name).id
        response = self._client.models_store_list_model_versions(project_id=teamspace_id, model_id=model_id)
        return response.versions

    def get_tree(self, teamspace_id: str, path: str, query_params: Optional[dict] = None) -> None:
        """Fetch the directory tree at ``path`` from the teamspace artifact REST API.

        Args:
            teamspace_id: ID of the teamspace.
            path: Artifact path to inspect.
            query_params: Extra query parameters merged with the auth token.

        Returns:
            Parsed JSON response from the server.
        """
        token = _authenticate_and_get_token(self._client)

        if query_params is None:
            query_params = {
                "token": token,
            }
        else:
            query_params["token"] = token
        r = requests.get(
            f"{self._client.api_client.configuration.host}/v1/projects/{teamspace_id}/artifacts/trees/{path}",
            params=query_params,
        )
        return r.json()

    def get_path_info(self, teamspace_id: str, path: str = "") -> dict:
        """Return existence, type, and size metadata for an artifact path.

        Args:
            teamspace_id: ID of the teamspace.
            path: Artifact path to check; empty string means root directory.

        Returns:
            Dict with keys ``exists`` (bool), ``type`` (``"file"``, ``"directory"``, or ``None``),
            and ``size`` (int bytes for files, ``None`` otherwise).
        """
        path = path.strip("/")

        if "/" in path:
            parent_path = path.rsplit("/", 1)[0]
            target_name = path.rsplit("/", 1)[1]
        else:
            if path == "":
                # root directory
                return {"exists": True, "type": "directory", "size": None}
            parent_path = ""
            target_name = path

        tree = self.get_tree(teamspace_id, path=parent_path)
        tree_items = tree.get("tree", [])
        for item in tree_items:
            item_name = item.get("path", "")
            if item_name == target_name:
                item_type = item.get("type")
                # if type == "blob" it's a file, if "tree" it's a directory
                return {
                    "exists": True,
                    "type": "file" if item_type == "blob" else "directory",
                    "size": item.get("size", 0) if item_type == "blob" else None,
                }
        warnings.warn(f"If '{path}' is a directory, it may be empty and thus not detected.")
        return {"exists": False, "type": None, "size": None}

    def list_files(
        self,
        teamspace_id: str,
        path: str = "",
    ) -> List[Dict]:
        """Recursively list all files in a directory tree.

        Args:
            teamspace_id: ID of the teamspace to list files in.
            path: Root path inside the teamspace to list; defaults to the root directory.

        Returns:
            List of file-info dicts from the recursive tree response.
        """
        path = path.strip("/")
        return self.get_tree(teamspace_id, path, query_params={"recursive": "true"}).get("tree", [])

    def upload_file(
        self,
        teamspace_id: str,
        cloud_account: str,
        file_path: str,
        remote_path: str,
        progress_bar: bool,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """Uploads file to given remote path in the Teamspace drive.

        Args:
            teamspace_id: ID of the owning teamspace.
            cloud_account: Cloud account ID to store the file on.
            file_path: Local filesystem path of the file to upload.
            remote_path: Destination path inside the Teamspace drive.
            progress_bar: Whether to display a progress bar during upload.
            headers: Optional extra HTTP headers to include in the upload request.
        """
        remote_path = remote_path.lstrip("/")
        if remote_path.startswith("teamspace/"):
            remote_path = remote_path[len("teamspace/") :]

        client_host = self._client.api_client.configuration.host
        endpoint_base = f"{client_host}/v1/projects/{teamspace_id}/artifacts"
        if remote_path.startswith(("uploads/", "Uploads/")):
            remote_path = remote_path[len("uploads/") :]
            endpoint_base = f"{client_host}/v1/projects/{teamspace_id}/artifacts/uploads"

        content_type = None
        extra_headers = dict(headers) if headers else None
        if extra_headers:
            # bind the content type into the signed URL; the rest ride along on the PUT
            content_type = extra_headers.pop("Content-Type", None)

        _BlobUploader(
            client=self._client,
            endpoint_base=endpoint_base,
            file_path=file_path,
            remote_path=remote_path,
            progress_bar=progress_bar,
            cluster_id=cloud_account,
            content_type=content_type,
            extra_headers=extra_headers or None,
        )()

    def download_file(
        self,
        path: str,
        target_path: str,
        teamspace_id: str,
        cloud_account: Optional[str] = None,
        progress_bar: bool = True,
    ) -> None:
        """Downloads a given file in Teamspace drive /Uploads/ to a target location.

        Args:
            path: Path of the file inside the Teamspace drive to download.
            target_path: Local filesystem path to write the downloaded file to.
            teamspace_id: ID of the owning teamspace.
            cloud_account: Optional cloud account ID used to locate the artifact.
            progress_bar: Whether to display a progress bar during download.
        """
        # TODO: Update this endpoint to permit basic auth
        token = _authenticate_and_get_token(self._client)

        query_params = {
            "token": token,
        }

        if cloud_account:
            query_params["clusterId"] = cloud_account

        r = requests.get(
            f"{self._client.api_client.configuration.host}/v1/projects/{teamspace_id}/artifacts/blobs/{path}",
            params=query_params,
            stream=True,
        )
        total_length = int(r.headers.get("content-length", 0))

        if progress_bar:
            pbar = tqdm(
                desc=f"Downloading {os.path.split(path)[1]}",
                total=total_length if total_length > 0 else None,
                unit="B",
                unit_scale=True,
                unit_divisor=1000,
            )

            pbar_update = pbar.update
        else:
            pbar_update = lambda x: None

        target_dir = os.path.split(target_path)[0]
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        with open(target_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=4096 * 8):
                f.write(chunk)
                pbar_update(len(chunk))

    def _download_single_file(
        self,
        file_info: Dict,
        base_path: str,
        download_dir: Path,
        teamspace_id: str,
        token: str,
        cloud_account: Optional[str] = None,
        pbar: Optional[tqdm] = True,
    ) -> None:
        """Download a single file from Teamspace drive with progress tracking.

        Args:
            file_info: Dict containing at least a ``"path"`` key with the file's artifact path.
            base_path: Base directory path prepended to the relative file path when building the request URL.
            download_dir: Local directory where the downloaded file is written.
            teamspace_id: ID of the owning teamspace.
            token: Authentication token for the artifact API.
            cloud_account: Optional cloud account ID used to locate the artifact.
            pbar: Optional tqdm progress bar to update as bytes are written.
        """
        relative_path = file_info["path"].lstrip("/")
        local_file = download_dir / relative_path
        local_file.parent.mkdir(parents=True, exist_ok=True)

        file_path = os.path.join(base_path, relative_path) if base_path else relative_path

        query_params = {
            "token": token,
        }
        if cloud_account:
            query_params["clusterId"] = cloud_account

        r = requests.get(
            f"{self._client.api_client.configuration.host}/v1/projects/{teamspace_id}/artifacts/blobs/{file_path}",
            params=query_params,
            stream=True,
        )

        with open(str(local_file), "wb") as f:
            for chunk in r.iter_content(chunk_size=4096 * 8):
                f.write(chunk)
                if pbar:
                    pbar.update(len(chunk))

    def download_folder(
        self,
        path: str,
        target_path: str,
        teamspace_id: str,
        cloud_account: Optional[str] = None,
        progress_bar: bool = True,
        num_workers: Optional[int] = None,
    ) -> None:
        """Downloads a given folder from Teamspace drive /Uploads/ to a target location.

        Args:
            path: Path of the folder inside the Teamspace drive to download.
            target_path: Local filesystem path to write the downloaded files to.
            teamspace_id: ID of the owning teamspace.
            cloud_account: Optional cloud account ID used to locate the artifacts.
            progress_bar: Whether to display a progress bar during download.
            num_workers: Number of parallel download threads; defaults to ``cpu_count * 4``.
        """
        # TODO: Update this endpoint to permit basic auth
        if num_workers is None:
            num_workers = os.cpu_count() * 4

        # Normalize the path
        path = path.strip("/")
        download_dir = Path(target_path)
        download_dir.mkdir(parents=True, exist_ok=True)

        files = self.list_files(teamspace_id, path)

        if not files:
            print(f"No files found in {path}")
            return

        token = _authenticate_and_get_token(self._client)

        total_size = sum(f.get("size", 0) for f in files)

        pbar = None
        if progress_bar:
            pbar = tqdm(
                desc="Downloading files",
                total=total_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1000,
                mininterval=1,
            )

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(
                    self._download_single_file,
                    file_info,
                    path,
                    download_dir,
                    teamspace_id,
                    token,
                    cloud_account,
                    pbar,
                )
                for file_info in files
            ]
            concurrent.futures.wait(futures)

        if pbar:
            pbar.set_description("Download complete")
            pbar.refresh()
            pbar.close()

    def get_secrets(self, teamspace_id: str) -> Dict[str, str]:
        """Get all secrets for a teamspace.

        Args:
            teamspace_id: ID of the teamspace to retrieve secrets for.

        Returns:
            Dict mapping secret names to a redacted placeholder string.
        """
        secrets = self._get_secrets(teamspace_id)
        # this returns encrypted values for security. It doesn't make sense to show them,
        # so we just return a placeholder
        # not a security issue to replace in the client as we get the encrypted values from the server.
        return {secret.name: "***REDACTED***" for secret in secrets if secret.type == V1SecretType.UNSPECIFIED}

    def set_secret(
        self,
        teamspace_id: str,
        key: str,
        value: str,
        secret_type: Union[str, SecretType] = SecretType.GENERIC,
    ) -> None:
        """Set a secret for a teamspace.

        This will replace the existing secret if it exists and create a new one if it doesn't.

        Args:
            teamspace_id: ID of the teamspace to set the secret in.
            key: Name of the secret to create or update.
            value: Value to store for the secret.
            secret_type: Type to tag the secret with when creating it, either a
                ``SecretType`` member or its string value (e.g. ``"hf_token"``). The
                update path does not change an existing secret's type.
        """
        resolved_type = _resolve_secret_type(secret_type)
        secrets = self._get_secrets(teamspace_id)
        for secret in secrets:
            if secret.name == key:
                return self._update_secret(teamspace_id, secret.id, value)
        return self._create_secret(teamspace_id, key, value, secret_type=resolved_type)

    def _get_secrets(self, teamspace_id: str) -> List[V1Secret]:
        """Fetch all raw secret objects for the teamspace.

        Args:
            teamspace_id: ID of the teamspace to fetch secrets for.

        Returns:
            List of ``V1Secret`` objects for the teamspace.
        """
        return self._client.secret_service_list_secrets(project_id=teamspace_id).secrets

    def _update_secret(self, teamspace_id: str, secret_id: str, value: str) -> None:
        """Overwrite the value of an existing teamspace secret by its ID.

        Args:
            teamspace_id: ID of the teamspace owning the secret.
            secret_id: Unique ID of the secret to update.
            value: New value to store for the secret.
        """
        self._client.secret_service_update_secret(
            body=SecretServiceUpdateSecretBody(value=value),
            project_id=teamspace_id,
            id=secret_id,
        )

    def _create_secret(
        self,
        teamspace_id: str,
        key: str,
        value: str,
        secret_type: V1SecretType = V1SecretType.UNSPECIFIED,
    ) -> None:
        """Create a new encrypted secret for the teamspace.

        Args:
            teamspace_id: ID of the teamspace to create the secret in.
            key: Name of the new secret.
            value: Value to store for the secret.
            secret_type: Type to tag the secret with.
        """
        self._client.secret_service_create_secret(
            body=SecretServiceCreateSecretBody(name=key, value=value, type=secret_type),
            project_id=teamspace_id,
        )

    def verify_secret_name(self, name: str) -> bool:
        """Verify if a secret name is valid.

        A valid secret name starts with a letter or underscore, followed by letters, digits, or underscores.

        Args:
            name: Secret name to validate.

        Returns:
            ``True`` if the name matches the valid pattern, ``False`` otherwise.
        """
        pattern = r"^[A-Za-z_][A-Za-z0-9_]*$"
        return re.match(pattern, name) is not None

    def new_folder(self, teamspace_id: str, name: str, cluster: Optional[V1ExternalCluster]) -> None:
        """Create a new managed storage folder data connection in the teamspace.

        Defaults to an R2 bucket when no cluster is provided, otherwise creates an S3 or GCS folder
        based on the cluster's cloud provider.

        Args:
            teamspace_id: ID of the teamspace to create the folder connection in.
            name: Name for the new data connection.
            cluster: Optional cloud account cluster to bind the storage to; uses R2 if ``None``.
        """
        create_request = DataConnectionServiceCreateDataConnectionBody(
            name=name,
            create_resources=True,
            force=True,
            writable=True,
        )

        if cluster is None:
            create_request.r2 = V1R2DataConnection(name=name)
        else:
            create_request.cluster_id = cluster.id
            create_request.access_cluster_ids = [cluster.id]

            if cluster.spec.aws_v1:
                create_request.s3_folder = V1S3FolderDataConnection()
            elif cluster.spec.google_cloud_v1:
                create_request.gcs_folder = V1GCSFolderDataConnection()

        self._client.data_connection_service_create_data_connection(create_request, teamspace_id)

    def new_connection(
        self, teamspace_id: str, name: str, source: str, cluster: V1ExternalCluster, writable: bool, region: str
    ) -> None:
        """Connect an existing external data source (e.g. EFS file system) to the teamspace.

        Args:
            teamspace_id: ID of the teamspace.
            name: Name for the data connection.
            source: External resource identifier (e.g. EFS file system ID).
            cluster: Cloud account cluster to bind the connection to.
            writable: Whether the connection should allow writes.
            region: AWS region where the external resource resides.
        """
        create_request = DataConnectionServiceCreateDataConnectionBody(
            name=name,
            create_resources=False,
            force=True,
            writable=writable,
            cluster_id=cluster.id,
            access_cluster_ids=[cluster.id],
        )

        # TODO: Add support for other connection types
        create_request.efs = V1EfsConfig(file_system_id=source, region=region)

        self._client.data_connection_service_create_data_connection(create_request, teamspace_id)
