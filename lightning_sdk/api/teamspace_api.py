import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from tqdm.auto import tqdm

from lightning_sdk.api.utils import (
    _download_model_files,
    _download_teamspace_files,
    _DummyBody,
    _FileUploader,
    _get_model_version,
    _ModelFileUploader,
    _resolve_teamspace_remote_path,
)
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi import (
    Externalv1LightningappInstance,
    ModelIdVersionsBody,
    ModelsStoreApi,
    ProjectIdAgentsBody,
    ProjectIdModelsBody,
    ProjectIdSecretsBody,
    SecretsIdBody,
    V1Assistant,
    V1CloudSpace,
    V1ClusterAccelerator,
    V1Endpoint,
    V1Job,
    V1LoginRequest,
    V1Model,
    V1ModelVersionArchive,
    V1MultiMachineJob,
    V1Project,
    V1ProjectClusterBinding,
    V1PromptSuggestion,
    V1Secret,
    V1SecretType,
    V1UpstreamOpenAI,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient

__all__ = ["TeamspaceApi"]


class TeamspaceApi:
    """Internal API client for Teamspace requests (mainly http requests)."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)
        self._models_api: Optional[ModelsStoreApi] = None

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

    def list_studios(self, teamspace_id: str, cloud_account: str = "") -> List[V1CloudSpace]:
        """List studios in teamspace."""
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
        """Lists cloud_accounts in a teamspace."""
        return self._client.projects_service_list_project_cluster_bindings(project_id=teamspace_id).clusters

    def _get_authed_user_id(self) -> str:
        """Gets the currently logged-in user."""
        auth = Auth()
        auth.authenticate()
        return auth.user_id

    def get_default_cloud_account(self, teamspace_id: str) -> str:
        """Get the default cloud account id of the teamspace."""
        return self._client.projects_service_get_project(teamspace_id).project_settings.preferred_cluster

    def _determine_cloud_account(self, teamspace_id: str) -> str:
        """Attempts to determine the cloud account id of the teamspace.

        Raises an error if it's ambiguous.

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

    # lazy property which is only created when needed
    @property
    def models_api(self) -> ModelsStoreApi:
        if not self._models_api:
            self._models_api = ModelsStoreApi(self._client.api_client)
        return self._models_api

    def get_model_version(self, name: str, version: Optional[str], teamspace_id: str) -> V1ModelVersionArchive:
        return _get_model_version(client=self._client, name=name, version=version, teamspace_id=teamspace_id)

    def create_model(
        self,
        name: str,
        version: Optional[str],
        metadata: Dict[str, str],
        private: bool,
        teamspace_id: str,
        cloud_account: str,
    ) -> V1ModelVersionArchive:
        # ask if such model already exists by listing models with specific name
        models = self.models_api.models_store_list_models(project_id=teamspace_id, name=name).models
        if len(models) == 0:
            return self.models_api.models_store_create_model(
                body=ProjectIdModelsBody(cluster_id=cloud_account, metadata=metadata, name=name, private=private),
                project_id=teamspace_id,
            )
        assert len(models) == 1, "Multiple models with the same name found"
        return self.models_api.models_store_create_model_version(
            body=ModelIdVersionsBody(cluster_id=cloud_account, version=version),
            project_id=teamspace_id,
            model_id=models[0].id,
        )

    def delete_model(self, name: str, version: Optional[str], teamspace_id: str) -> None:
        """Delete a model or a version from the model store."""
        model = self.get_model(teamspace_id=teamspace_id, model_name=name)
        # decide if delete only version of whole model
        if version:
            if version == "default":
                version = model.default_version
            self.models_api.models_store_delete_model_version(
                project_id=teamspace_id, model_id=model.id, version=version
            )
        else:
            self.models_api.models_store_delete_model(project_id=teamspace_id, model_id=model.id)

    def upload_model_file(
        self,
        model_id: str,
        version: str,
        local_path: Path,
        remote_path: str,
        teamspace_id: str,
        progress_bar: bool = True,
    ) -> None:
        """Upload a file to the model store."""
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
        """Upload files to the model store."""
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
        self.models_api.models_store_complete_model_upload(
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

    def list_jobs(self, teamspace_id: str) -> Tuple[List[Externalv1LightningappInstance], List[V1Job]]:
        apps = self._client.lightningapp_instance_service_list_lightningapp_instances(
            project_id=teamspace_id, source_app="job_run_plugin"
        ).lightningapps
        jobs = self._client.jobs_service_list_jobs(project_id=teamspace_id, standalone=True).jobs

        return apps, jobs

    def list_mmts(self, teamspace_id: str) -> Tuple[List[Externalv1LightningappInstance], List[V1MultiMachineJob]]:
        apps = self._client.lightningapp_instance_service_list_lightningapp_instances(
            project_id=teamspace_id, source_app="distributed_plugin"
        ).lightningapps
        jobs = self._client.jobs_service_list_multi_machine_jobs(project_id=teamspace_id).multi_machine_jobs
        return apps, jobs

    def list_machines(self, teamspace_id: str, cloud_account: str) -> List[V1ClusterAccelerator]:
        response = self._client.cluster_service_list_project_cluster_accelerators(
            project_id=teamspace_id, id=cloud_account
        )
        return response.accelerator

    def get_model(self, teamspace_id: str, model_id: Optional[str] = None, model_name: Optional[str] = None) -> V1Model:
        if model_id:
            return self.models_api.models_store_get_model(project_id=teamspace_id, model_id=model_id)
        if not model_name:
            raise ValueError("Either `model_id` or `model_name` must be provided.")
        # list models with specific name
        models = self.models_api.models_store_list_models(project_id=teamspace_id, name=model_name).models
        if len(models) == 0:
            raise ValueError(f"Model '{model_name}' does not exist.")
        if len(models) > 1:
            raise RuntimeError(f"Model name '{model_name}' is not a unique with this teamspace.")
        # if there is only one model with the name, return it
        return models[0]

    def list_models(self, teamspace_id: str) -> List[V1Model]:
        response = self.models_api.models_store_list_models(project_id=teamspace_id)
        return response.models

    def list_model_versions(
        self, teamspace_id: str, model_id: Optional[str] = None, model_name: Optional[str] = None
    ) -> List[V1ModelVersionArchive]:
        if model_name and not model_id:
            model_id = self.get_model(teamspace_id=teamspace_id, model_name=model_name).id
        response = self.models_api.models_store_list_model_versions(project_id=teamspace_id, model_id=model_id)
        return response.versions

    def upload_file(
        self,
        teamspace_id: str,
        cloud_account: str,
        file_path: str,
        remote_path: str,
        progress_bar: bool,
    ) -> None:
        """Uploads file to given remote path in the Teamspace drive."""
        _FileUploader(
            client=self._client,
            teamspace_id=teamspace_id,
            cloud_account=cloud_account,
            file_path=file_path,
            remote_path=_resolve_teamspace_remote_path(remote_path),
            progress_bar=progress_bar,
        )()

    def download_file(
        self,
        path: str,
        target_path: str,
        teamspace_id: str,
        cloud_account: str,
        progress_bar: bool = True,
    ) -> None:
        """Downloads a given file in Teamspace drive to a target location."""
        # TODO: Update this endpoint to permit basic auth
        auth = Auth()
        auth.authenticate()
        token = self._client.auth_service_login(V1LoginRequest(auth.api_key)).token

        query_params = {
            "clusterId": cloud_account,
            "key": _resolve_teamspace_remote_path(path),
            "token": token,
        }

        r = requests.get(
            f"{self._client.api_client.configuration.host}/v1/projects/{teamspace_id}/artifacts/download",
            params=query_params,
            stream=True,
        )
        total_length = int(r.headers.get("content-length"))

        if progress_bar:
            pbar = tqdm(
                desc=f"Downloading {os.path.split(path)[1]}",
                total=total_length,
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

    def download_folder(
        self,
        path: str,
        target_path: str,
        teamspace_id: str,
        cloud_account: str,
        progress_bar: bool = True,
    ) -> None:
        """Downloads a given folder from Teamspace drive to a target location."""
        # TODO: Update this endpoint to permit basic auth
        auth = Auth()
        auth.authenticate()

        prefix = _resolve_teamspace_remote_path(path)

        # ensure we only download as a directory and not the entire prefix
        if prefix.endswith("/") is False:
            prefix = prefix + "/"

        _download_teamspace_files(
            client=self._client,
            teamspace_id=teamspace_id,
            cluster_id=cloud_account,
            prefix=prefix,
            download_dir=Path(target_path),
            progress_bar=progress_bar,
        )

    def get_secrets(self, teamspace_id: str) -> Dict[str, str]:
        """Get all secrets for a teamspace."""
        secrets = self._get_secrets(teamspace_id)
        # this returns encrypted values for security. It doesn't make sense to show them,
        # so we just return a placeholder
        # not a security issue to replace in the client as we get the encrypted values from the server.
        return {secret.name: "***REDACTED***" for secret in secrets if secret.type == V1SecretType.UNSPECIFIED}

    def set_secret(self, teamspace_id: str, key: str, value: str) -> None:
        """Set a secret for a teamspace.

        This will replace the existing secret if it exists and create a new one if it doesn't.
        """
        secrets = self._get_secrets(teamspace_id)
        for secret in secrets:
            if secret.name == key:
                return self._update_secret(teamspace_id, secret.id, value)
        return self._create_secret(teamspace_id, key, value)

    def _get_secrets(self, teamspace_id: str) -> List[V1Secret]:
        return self._client.secret_service_list_secrets(project_id=teamspace_id).secrets

    def _update_secret(self, teamspace_id: str, secret_id: str, value: str) -> None:
        self._client.secret_service_update_secret(
            body=SecretsIdBody(value=value),
            project_id=teamspace_id,
            id=secret_id,
        )

    def _create_secret(
        self,
        teamspace_id: str,
        key: str,
        value: str,
    ) -> None:
        self._client.secret_service_create_secret(
            body=ProjectIdSecretsBody(name=key, value=value, type=V1SecretType.UNSPECIFIED), project_id=teamspace_id
        )

    def verify_secret_name(self, name: str) -> bool:
        """Verify if a secret name is valid.

        A valid secret name starts with a letter or underscore, followed by letters, digits, or underscores.
        """
        pattern = r"^[A-Za-z_][A-Za-z0-9_]*$"
        return re.match(pattern, name) is not None
