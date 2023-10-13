import os
import tarfile
import tempfile
import time
from typing import Dict, Optional, Tuple
import math

import requests

from lightning_sdk.lightning_cloud.openapi import (
    CloudspaceIdRunsBody,
    IdCodeconfigBody,
    IdExecuteBody,
    IdForkBody,
    ProjectIdCloudspacesBody,
    V1CloudSpace,
    V1CloudSpaceInstanceConfig,
    V1GetCloudSpaceInstanceStatusResponse,
    V1UserRequestedComputeConfig,
    ProjectIdStorageBody, StorageMultipartBody,
    V1CreateMultipartUploadProjectArtifactResponse,
    V1MultiPartPresignedUrl, MultipartCompleteBody,
    V1CompleteMultiPartUpload
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.machine import Machine

import os
from tqdm import tqdm
from tqdm.utils import CallbackIOWrapper
import requests

_BYTES_PER_KB = 1000
_BYTES_PER_MB = 1000 * _BYTES_PER_KB
_BYTES_PER_GB = 1000 * _BYTES_PER_MB

_SIZE_LIMIT_SINGLE_PART = 5 * _BYTES_PER_GB
_MAX_SIZE_MULTI_PART_CHUNK = 20 * _BYTES_PER_MB


class StudioApi:
    """Internal API client for Studio requests (mainly http requests)."""

    def __init__(self) -> None:
        super().__init__()

        self._cloud_url = _cloud_url()
        self._client = LightningClient()

    def get_studio(
        self,
        name: str,
        teamspace_id: str,
    ) -> V1CloudSpace:
        """Gets the current studio corresponding to the given name in the given teamspace."""
        res = self._client.cloud_space_service_list_cloud_spaces(project_id=teamspace_id)
        _studio = [el for el in res.cloudspaces if el.display_name == name or el.name == name]
        if not _studio:
            raise ValueError(f"Studio {name} does not exist")
        return _studio[0]

    def create_studio(
        self,
        name: str,
        teamspace_id: str,
        cluster: Optional[str] = None,
    ) -> V1CloudSpace:
        """Create a Studio with a given name in a given Teamspace on a possibly given cluster."""
        body = ProjectIdCloudspacesBody(
            cluster_id=cluster,
            name=name,
            display_name=name,
        )
        studio = self._client.cloud_space_service_create_cloud_space(body, teamspace_id)

        run_body = CloudspaceIdRunsBody(
            cluster_id=cluster,
            local_source=True,
        )
        run = self._client.cloud_space_service_create_lightning_run(
            project_id=teamspace_id, cloudspace_id=studio.id, body=run_body
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            main_py_path = os.path.join(tmpdir, "main.py")
            with open(main_py_path, "w") as f:
                f.write("print('Hello, Lightning World!')\n")

            # TODO: Explore ways to do this without writing a file
            tar_path = os.path.join(tmpdir, "source.tar.gz")
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(main_py_path, arcname="main.py")

            with open(tar_path, "rb") as fo:
                requests.put(run.source_upload_url, data=fo)
        return studio

    def get_studio_status(self, studio_id: str, teamspace_id: str) -> V1GetCloudSpaceInstanceStatusResponse:
        """Gets the current (internal) Studio status."""
        return self._client.cloud_space_service_get_cloud_space_instance_status(
            project_id=teamspace_id,
            id=studio_id,
        )

    def start_studio(self, studio_id: str, teamspace_id: str) -> None:
        """Start an existing Studio."""
        self._client.cloud_space_service_start_cloud_space_instance(teamspace_id, studio_id)

        while self.get_studio_status(studio_id, teamspace_id).in_use.sync_in_progress:
            time.sleep(1)

        while int(self.get_studio_status(studio_id, teamspace_id).in_use.startup_percentage) < 100:
            time.sleep(1)

    def stop_studio(self, studio_id: str, teamspace_id: str) -> None:
        """Stop an existing Studio."""
        # TODO: Wait for it to be stopped? This would match the time a user actually pays for an instance then
        self._client.cloud_space_service_stop_cloud_space_instance(
            project_id=teamspace_id,
            id=studio_id,
        )

    def switch_studio_machine(self, studio_id: str, teamspace_id: str, machine: Machine) -> None:
        """Switches given Studio to a new machine type."""
        compute_name = _MACHINE_TO_COMPUTE_NAME[machine]
        # TODO: UI sends disk size here, maybe we need to also?
        body = IdCodeconfigBody(compute_config=V1UserRequestedComputeConfig(name=compute_name))
        self._client.cloud_space_service_update_cloud_space_instance_config(
            id=studio_id,
            project_id=teamspace_id,
            body=body,
        )

        while int(self.get_studio_status(studio_id, teamspace_id).requested.startup_percentage) < 100:
            time.sleep(1)

        self._client.cloud_space_service_switch_cloud_space_instance(teamspace_id, studio_id)

    def get_machine(self, studio_id: str, teamspace_id: str) -> Machine:
        """Get the current machine type the given Studio is running on."""
        response: V1CloudSpaceInstanceConfig = self._client.cloud_space_service_get_cloud_space_instance_config(
            project_id=teamspace_id, id=studio_id
        )
        return _COMPUTE_NAME_TO_MACHINE[response.compute_config.name]

    def run_studio_commands(self, studio_id: str, teamspace_id: str, *commands: str) -> Tuple[str, int]:
        """Run given commands in a given Studio."""
        response = self._client.cloud_space_service_execute_command_in_cloud_space(
            IdExecuteBody("; ".join(commands)), project_id=teamspace_id, id=studio_id
        )
        return response.output, response.exit_code

    def duplicate_studio(self, studio_id: str, teamspace_id: str, target_teamspace_id: str) -> Dict[str, str]:
        """Duplicates the given Studio from a given Teamspace into a given target Teamspace."""
        target_teamspace = self._client.projects_service_get_project(target_teamspace_id)
        init_kwargs = {}
        if target_teamspace.owner_type == "user":
            from lightning_sdk.api.user_api import UserApi

            init_kwargs["user"] = UserApi()._get_user_by_id(target_teamspace.owner_id).username
        elif target_teamspace.owner_type == "organization":
            from lightning_sdk.api.org_api import OrgApi

            init_kwargs["org"] = OrgApi()._get_org_by_id(target_teamspace.owner_id).name

        new_cloudspace = self._client.cloud_space_service_fork_cloud_space(
            IdForkBody(target_project_id=target_teamspace_id), project_id=teamspace_id, id=studio_id
        )

        init_kwargs["name"] = new_cloudspace.name
        init_kwargs["teamspace"] = target_teamspace.name

        self.start_studio(new_cloudspace.id, target_teamspace_id)
        return init_kwargs

    def delete_studio(self, studio_id: str, teamspace_id: str) -> None:
        """Delete existing given Studio."""
        self._client.cloud_space_service_delete_cloud_space(project_id=teamspace_id, id=studio_id)

    def upload_file(self, studio_id: str, teamspace_id: str, cluster_id: str, filepath: str, remote_path: str, progress_bar: bool = True):

        # todo: validation that remote part is within home directory
        remote_path = f"/cloudspaces/{studio_id}/code/content/{remote_path}"
        if os.path.getsize(filepath) <= _SIZE_LIMIT_SINGLE_PART:
            return self._single_part_upload(teamspace_id=teamspace_id, cluster_id=cluster_id, filepath=filepath, remote_path=remote_path, progress_bar=progress_bar)

        return self._multipart_upload(teamspace_id=teamspace_id, cluster_id=cluster_id, filepath=filepath, remote_path=remote_path, progress_bar=progress_bar)


    def _single_part_upload(self, teamspace_id: str, cluster_id: str, filepath: str, remote_path: str, progress_bar: bool):

        body = ProjectIdStorageBody(cluster_id=cluster_id, filename=remote_path)
        url = self._client.lightningapp_instance_service_upload_project_artifact(body, project_id=teamspace_id).upload_url
        _upload_file_to_urls(url, path=filepath, progress_bar=progress_bar)

    def _multipart_upload(self, teamspace_id: str, cluster_id: str, filepath: str, remote_path: str, progress_bar: bool):
        remote_path = f"projects/{teamspace_id}" + remote_path

        count = math.ceil(os.path.getsize(filepath) / _MAX_SIZE_MULTI_PART_CHUNK)

        body = StorageMultipartBody(cluster_id=cluster_id, count=count, filename=remote_path)
        resp: V1CreateMultipartUploadProjectArtifactResponse = self._client.lightningapp_instance_service_create_multipart_upload_project_artifact(body=body, project_id=teamspace_id)
        
        completed = _upload_file_to_urls(*resp.urls, path=filepath, progress_bar=progress_bar)

        completed_body = MultipartCompleteBody(cluster_id=cluster_id, filename=remote_path, parts=completed, upload_id=resp.upload_id)
        self._client.lightningapp_instance_service_complete_multipart_upload_project_artifact(body=completed_body, project_id=teamspace_id)

    def list_files(self, path: Optional[str], studio_id: str, teamspace_id: str, cluster_id: str, return_url: bool):
        kwargs = {
            "project_id": teamspace_id,
            "id": studio_id,
            "cluster_id": cluster_id,
            "include_download_url": return_url,
        }

        if path is not None:
            kwargs["prefix"] = "/" + path
        resp = self._client.cloud_space_service_get_cloud_space_artifacts_page(**kwargs)

        artifacts = {}
        
        strip_prefix = f"projects{teamspace_id}/cloudspaces/{studio_id}/code/content/"
        if path is not None:
            strip_prefix = strip_prefix + path.strip("/") + "/"
        for art in resp.artifacts:
            filename = art.filename.strip()
            if path is None or filename.startswith(path):
                artifacts[filename] = {"last_modified": art.last_modified, "md5_checksum": art.md5_checksum, "size_bytes": art.size_bytes}

                if return_url:
                    artifacts[filename]["download_url"] = art.url

        return artifacts

    def download_file(self, path: str, target_path: str, studio_id: str, teamspace_id: str, cluster_id: str, progress_bar: bool = True):
        files = self.list_files(path, studio_id, teamspace_id, cluster_id, return_url=True)
        files[path].url

        r = requests.get(files[path].url, stream=True)
        total_length = int(r.headers.get('content-length'))
            
        if progress_bar:
            pbar = tqdm(
                desc=f"Downloading {os.path.split(path)[1]}",
                total=total_length,
                unit="B",
                unit_scale=True,
                unit_divisor=1000,)

            pbar_update = pbar.update
        else:
            pbar_update = lambda x: None

        with open(target_path, "wb"):
            for chunk in r.iter_content():
                f.write(chunk)
                f.flush()
                pbar_update(len(chunk))
    
def _upload_file_to_urls(*urls, path: str, progress_bar: bool=True) -> None:

    if progress_bar:
        file_size = os.path.getsize(path)
        pbar = tqdm(
            desc=f"Uploading {os.path.split(path)[1]}",
            total=file_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1000,
        )
        update_fn = pbar.update

    else:
        update_fn = lambda *args, **kwargs: None

    is_multipart = len(urls) > 1
    completed_uploads = []

    with open(path, "rb") as fd:
        reader_wrapper = CallbackIOWrapper(update_fn, fd, "read")
    
        for url in urls:
            if is_multipart:
                assert isinstance(url, V1MultiPartPresignedUrl)
                # unfortunately we can't just pass the reader_wrapper directly since we only need to read the first N bytes, 
                # I wasn't yet able to figure out how to make it work, but it likely would be a bit faster
                data = reader_wrapper.read(_MAX_SIZE_MULTI_PART_CHUNK)
                curr_url = url.url
            else:
                data = reader_wrapper
                curr_url = url
            
            response = requests.put(curr_url, data=data)
            response.raise_for_status()

            if is_multipart:
                etag = response.headers.get("ETag")
                completed_uploads.append(V1CompleteMultiPartUpload(etag=etag, part_number=url.part_number))

    if progress_bar:
        pbar.close()
        
    return completed_uploads
            

def _cloud_url() -> str:
    # set cloud url with default url if not set before
    cloud_url = os.environ.get("LIGHTNING_CLOUD_URL", _DEFAULT_CLOUD_URL)
    os.environ["LIGHTNING_CLOUD_URL"] = cloud_url
    return cloud_url


# TODO: This should really come from some kind of metadata service
# TODO: Add trainium instances once feature flag is lifted
_MACHINE_TO_COMPUTE_NAME: Dict[Machine, str] = {
    Machine.CPU: "cpu-4",
    Machine.DATA_PREP: "data-large-8000",
    Machine.T4: "g4dn.2xlarge",
    Machine.T4_X_4: "g4dn.12xlarge",
    Machine.V100: "p3.2xlarge",
    Machine.V100_X_4: "p3.8xlarge",
    Machine.A10G: "g5.8xlarge",
    Machine.A10G_X_4: "g5.12xlarge",
    Machine.A100_X_8: "p4d.24xlarge",
}

_COMPUTE_NAME_TO_MACHINE: Dict[str, Machine] = {v: k for k, v in _MACHINE_TO_COMPUTE_NAME.items()}

_DEFAULT_CLOUD_URL = "https://lightning.ai:443"
