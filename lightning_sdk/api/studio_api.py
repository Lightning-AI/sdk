import math
import os
import tarfile
import tempfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import backoff
import requests

from lightning_sdk.constants import _LIGHTNING_DEBUG
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi import (
    CloudspaceIdRunsBody,
    Externalv1LightningappInstance,
    IdCodeconfigBody,
    IdExecuteBody,
    IdForkBody,
    IdStartBody,
    ProjectIdCloudspacesBody,
    ProjectIdStorageBody,
    StorageCompleteBody,
    UploadsUploadIdBody,
    V1CloudSpace,
    V1CloudSpaceInstanceConfig,
    V1CloudSpaceState,
    V1CompleteUpload,
    V1GetCloudSpaceInstanceStatusResponse,
    V1GetLongRunningCommandInCloudSpaceResponse,
    V1LoginRequest,
    V1Plugin,
    V1PluginsListResponse,
    V1PresignedUrl,
    V1UploadProjectArtifactPartsResponse,
    V1UploadProjectArtifactResponse,
    V1UserRequestedComputeConfig,
)

try:
    from lightning_sdk.lightning_cloud.openapi import AppsIdBody1 as AppsIdBody
except ImportError:
    from lightning_sdk.lightning_cloud.openapi import AppsIdBody

import json

from tqdm import tqdm
from tqdm.utils import CallbackIOWrapper

from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.machine import Machine

_BYTES_PER_KB = 1000
_BYTES_PER_MB = 1000 * _BYTES_PER_KB
_BYTES_PER_GB = 1000 * _BYTES_PER_MB

_SIZE_LIMIT_SINGLE_PART = 5 * _BYTES_PER_GB
_MAX_SIZE_MULTI_PART_CHUNK = 100 * _BYTES_PER_MB
_MAX_BATCH_SIZE = 50
_MAX_WORKERS = 10


class StudioApi:
    """Internal API client for Studio requests (mainly http requests)."""

    def __init__(self) -> None:
        super().__init__()

        self._cloud_url = _cloud_url()
        self._client = LightningClient(max_tries=3)

    def get_studio(
        self,
        name: str,
        teamspace_id: str,
    ) -> V1CloudSpace:
        """Gets the current studio corresponding to the given name in the given teamspace."""
        res = self._client.cloud_space_service_list_cloud_spaces(project_id=teamspace_id, name=name)
        if not res.cloudspaces:
            raise ValueError(f"Studio {name} does not exist")
        return res.cloudspaces[0]

    def get_studio_by_id(
        self,
        studio_id: str,
        teamspace_id: str,
    ) -> V1CloudSpace:
        """Gets the current studio corresponding to the passed id."""
        return self._client.cloud_space_service_get_cloud_space(project_id=teamspace_id, id=studio_id)

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
            cluster_id=studio.cluster_id,
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

            with open(tar_path, "rb") as fopen:
                requests.put(run.source_upload_url, data=fopen)
        return studio

    def get_studio_status(self, studio_id: str, teamspace_id: str) -> V1GetCloudSpaceInstanceStatusResponse:
        """Gets the current (internal) Studio status."""
        return self._client.cloud_space_service_get_cloud_space_instance_status(
            project_id=teamspace_id,
            id=studio_id,
        )

    def start_studio(self, studio_id: str, teamspace_id: str, machine: Machine) -> None:
        """Start an existing Studio."""
        self._client.cloud_space_service_start_cloud_space_instance(
            IdStartBody(compute_config=V1UserRequestedComputeConfig(name=_MACHINE_TO_COMPUTE_NAME[machine])),
            teamspace_id,
            studio_id,
        )

        while self.get_studio_status(studio_id, teamspace_id).in_use.sync_in_progress:
            time.sleep(1)

        while int(self.get_studio_status(studio_id, teamspace_id).in_use.startup_percentage) < 100:
            time.sleep(1)

        if _LIGHTNING_DEBUG:
            code_status = self.get_studio_status(studio_id, teamspace_id)
            instance_id = code_status.in_use.cloud_space_instance_id
            print(f"Studio started | {teamspace_id=} {studio_id=} {instance_id=}")

    def stop_studio(self, studio_id: str, teamspace_id: str) -> None:
        """Stop an existing Studio."""
        # TODO: Wait for it to be stopped? This would match the time a user actually pays for an instance then
        self._client.cloud_space_service_stop_cloud_space_instance(
            project_id=teamspace_id,
            id=studio_id,
        )

        # block until studio is really stopped
        while self._get_studio_instance_status(studio_id=studio_id, teamspace_id=teamspace_id) not in (
            None,
            "CLOUD_SPACE_INSTANCE_STATE_STOPPED",
        ):
            time.sleep(1)

    def _get_studio_instance_status(self, studio_id: str, teamspace_id: str) -> Optional[str]:
        """Returns status of the in-use instance of the Studio."""
        internal_status = self.get_studio_status(studio_id=studio_id, teamspace_id=teamspace_id).in_use
        if internal_status is None:
            return None

        return internal_status.phase

    def _request_switch(self, studio_id: str, teamspace_id: str, machine: Machine) -> None:
        """Switches given Studio to a new machine type."""
        compute_name = _MACHINE_TO_COMPUTE_NAME[machine]
        # TODO: UI sends disk size here, maybe we need to also?
        body = IdCodeconfigBody(compute_config=V1UserRequestedComputeConfig(name=compute_name))
        self._client.cloud_space_service_update_cloud_space_instance_config(
            id=studio_id,
            project_id=teamspace_id,
            body=body,
        )

    def switch_studio_machine(self, studio_id: str, teamspace_id: str, machine: Machine) -> None:
        """Switches given Studio to a new machine type."""
        self._request_switch(studio_id=studio_id, teamspace_id=teamspace_id, machine=machine)

        while int(self.get_studio_status(studio_id, teamspace_id).requested.startup_percentage) < 100:
            time.sleep(1)

        self._client.cloud_space_service_switch_cloud_space_instance(teamspace_id, studio_id)

    def get_machine(self, studio_id: str, teamspace_id: str) -> Machine:
        """Get the current machine type the given Studio is running on."""
        response: V1CloudSpaceInstanceConfig = self._client.cloud_space_service_get_cloud_space_instance_config(
            project_id=teamspace_id, id=studio_id
        )
        return _COMPUTE_NAME_TO_MACHINE[response.compute_config.name]

    def _get_detached_command_status(
        self, studio_id: str, teamspace_id: str, session_id: str
    ) -> V1GetLongRunningCommandInCloudSpaceResponse:
        """Get the status of a detached command."""
        resp = self._client.cloud_space_service_get_long_running_command_in_cloud_space(
            project_id=teamspace_id, id=studio_id, session=session_id
        )
        if not resp:
            raise RuntimeError("Unable to get status of running command")
        return resp

    def run_studio_commands(self, studio_id: str, teamspace_id: str, *commands: str) -> Tuple[str, int]:
        """Run given commands in a given Studio."""
        session_id = str(uuid4())
        response_submit = self._client.cloud_space_service_execute_command_in_cloud_space(
            IdExecuteBody("; ".join(commands), detached=True, session_name=session_id),
            project_id=teamspace_id,
            id=studio_id,
        )

        if not response_submit:
            raise RuntimeError("Unable to submit command")

        while True:
            resp = self._get_detached_command_status(
                studio_id=studio_id, teamspace_id=teamspace_id, session_id=session_id
            )
            if resp.exit_code != -1:
                return resp.output, resp.exit_code

            time.sleep(1)

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

        while self.get_studio_by_id(new_cloudspace.id, target_teamspace_id).state != V1CloudSpaceState.READY:
            time.sleep(1)

        init_kwargs["name"] = new_cloudspace.name
        init_kwargs["teamspace"] = target_teamspace.name

        self.start_studio(new_cloudspace.id, target_teamspace_id, Machine.CPU)
        return init_kwargs

    def delete_studio(self, studio_id: str, teamspace_id: str) -> None:
        """Delete existing given Studio."""
        self._client.cloud_space_service_delete_cloud_space(project_id=teamspace_id, id=studio_id)

    def upload_file(
        self,
        studio_id: str,
        teamspace_id: str,
        cluster_id: str,
        file_path: str,
        remote_path: str,
    ) -> None:
        """Uploads file to given remote path on the studio."""
        _FileUploader(
            client=self._client,
            studio_id=studio_id,
            teamspace_id=teamspace_id,
            cluster_id=cluster_id,
            file_path=file_path,
            remote_path=remote_path,
        )()

    def download_file(
        self, path: str, target_path: str, studio_id: str, teamspace_id: str, cluster_id: str, progress_bar: bool = True
    ) -> None:
        """Downloads a given file from a Studio to a target location."""
        # TODO: Update this endpoint to permit basic auth
        auth = Auth()
        auth.authenticate()
        token = self._client.auth_service_login(V1LoginRequest(auth.api_key)).token

        query_params = {
            "clusterId": cluster_id,
            "key": f"/cloudspaces/{studio_id}/code/content/{path}",
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
        self, path: str, target_path: str, studio_id: str, teamspace_id: str, cluster_id: str, progress_bar: bool = True
    ) -> None:
        """Downloads a given folder from a Studio to a target location."""
        # TODO: Update this endpoint to permit basic auth
        auth = Auth()
        auth.authenticate()
        token = self._client.auth_service_login(V1LoginRequest(auth.api_key)).token

        query_params = {
            "clusterId": cluster_id,
            "prefix": f"/cloudspaces/{studio_id}/code/content/{path}",
            "token": token,
        }

        r = requests.get(
            f"{self._client.api_client.configuration.host}/v1/projects/{teamspace_id}/artifacts/download",
            params=query_params,
            stream=True,
        )

        if progress_bar:
            pbar = tqdm(
                desc=f"Downloading {os.path.split(path)[1]}",
                unit="B",
                unit_scale=True,
                unit_divisor=1000,
            )

            pbar_update = pbar.update
        else:
            pbar_update = lambda x: None

        if target_path:
            os.makedirs(target_path, exist_ok=True)

        with tempfile.TemporaryFile() as f:
            for chunk in r.iter_content(chunk_size=4096 * 8):
                f.write(chunk)
                pbar_update(len(chunk))

            with zipfile.ZipFile(f) as z:
                z.extractall(target_path)

    def install_plugin(self, studio_id: str, teamspace_id: str, plugin_name: str) -> str:
        """Installs the given plugin."""
        resp: V1Plugin = self._client.cloud_space_service_install_plugin(
            project_id=teamspace_id, id=studio_id, plugin_id=plugin_name
        )
        if not (resp.state == "installation_success" and resp.error == ""):
            raise RuntimeError(f"Failed to install plugin {plugin_name}: {resp.error}")

        additional_info = resp.additional_info or ""

        return additional_info.strip("\n").strip()

    def uninstall_plugin(self, studio_id: str, teamspace_id: str, plugin_name: str) -> None:
        """Uninstalls the given plugin."""
        resp: V1Plugin = self._client.cloud_space_service_uninstall_plugin(
            project_id=teamspace_id, id=studio_id, plugin_id=plugin_name
        )
        if not (resp.state == "uninstallation_success" and resp.error == ""):
            raise RuntimeError(f"Failed to uninstall plugin {plugin_name}: {resp.error}")

    def execute_plugin(self, studio_id: str, teamspace_id: str, plugin_name: str) -> Tuple[str, int]:
        """Executes the given plugin."""
        resp: V1Plugin = self._client.cloud_space_service_execute_plugin(
            project_id=teamspace_id, id=studio_id, plugin_id=plugin_name
        )
        if not (resp.state == "execution_success" and resp.error == ""):
            raise RuntimeError(f"Failed to execute plugin {plugin_name}: {resp.error}")

        additional_info_string = resp.additional_info
        additional_info = json.loads(additional_info_string)
        port = int(additional_info["port"])

        output_str = ""

        # if port is specified greater than 0 this means the plugin is interactive.
        # Prompt the user to head to the browser
        if port > 0:
            output_str = (
                f"Plugin {plugin_name} is interactive. Have a look at https://{port}-{studio_id}.cloudspaces.litng.ai"
            )

        elif port < 0:
            output_str = "This plugin can only be used on the browser interface of a Studio!"

        # TODO: retrieve actual command output?
        elif port == 0:
            output_str = f"Successfully executed plugin {plugin_name}"

        return output_str, port

    def list_available_plugins(self, studio_id: str, teamspace_id: str) -> Dict[str, str]:
        """Lists the available plugins."""
        resp: V1PluginsListResponse = self._client.cloud_space_service_list_available_plugins(
            project_id=teamspace_id, id=studio_id
        )
        return resp.plugins

    def list_installed_plugins(self, studio_id: str, teamspace_id: str) -> Dict[str, str]:
        """Lists all installed plugins."""
        resp: V1PluginsListResponse = self._client.cloud_space_service_list_installed_plugins(
            project_id=teamspace_id, id=studio_id
        )
        return resp.plugins

    def create_job(
        self, entrypoint: str, name: str, machine: Machine, studio_id: str, teamspace_id: str, cluster_id: str
    ) -> Externalv1LightningappInstance:
        """Creates a job with given commands."""
        return self._create_app(
            studio_id=studio_id,
            teamspace_id=teamspace_id,
            cluster_id=cluster_id,
            plugin_type="job",
            entrypoint=entrypoint,
            name=name,
            compute=_MACHINE_TO_COMPUTE_NAME[machine],
        )

    def create_multi_machine_job(
        self,
        entrypoint: str,
        name: str,
        num_instances: int,
        machine: Machine,
        strategy: str,
        studio_id: str,
        teamspace_id: str,
        cluster_id: str,
    ) -> Externalv1LightningappInstance:
        """Creates a multi-machine job with given commands."""
        distributed_args = {
            "cloud_compute": _MACHINE_TO_COMPUTE_NAME[machine],
            "num_instances": num_instances,
            "strategy": strategy,
        }
        return self._create_app(
            studio_id=studio_id,
            teamspace_id=teamspace_id,
            cluster_id=cluster_id,
            plugin_type="distributed_plugin",
            entrypoint=entrypoint,
            name=name,
            distributedArguments=json.dumps(distributed_args),
        )

    def create_data_prep_machine_job(
        self,
        entrypoint: str,
        name: str,
        num_instances: int,
        machine: Machine,
        studio_id: str,
        teamspace_id: str,
        cluster_id: str,
    ) -> Externalv1LightningappInstance:
        """Creates a multi-machine job with given commands."""
        data_prep_args = {
            "cloud_compute": _MACHINE_TO_COMPUTE_NAME[machine],
            "num_instances": num_instances,
        }
        return self._create_app(
            studio_id=studio_id,
            teamspace_id=teamspace_id,
            cluster_id=cluster_id,
            plugin_type="data_prep",
            entrypoint=entrypoint,
            name=name,
            dataPrepArguments=json.dumps(data_prep_args),
        )

    def create_inference_job(
        self,
        entrypoint: str,
        name: str,
        machine: Machine,
        min_replicas: str,
        max_replicas: str,
        max_batch_size: str,
        timeout_batching: str,
        scale_in_interval: str,
        scale_out_interval: str,
        endpoint: str,
        studio_id: str,
        teamspace_id: str,
        cluster_id: str,
    ) -> Externalv1LightningappInstance:
        """Creates an inference job for given endpoint."""
        return self._create_app(
            studio_id=studio_id,
            teamspace_id=teamspace_id,
            cluster_id=cluster_id,
            plugin_type="inference_plugin",
            compute=_MACHINE_TO_COMPUTE_NAME[machine],
            entrypoint=entrypoint,
            name=name,
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            max_batch_size=max_batch_size,
            timeout_batching=timeout_batching,
            scale_in_interval=scale_in_interval,
            scale_out_interval=scale_out_interval,
            endpoint=endpoint,
        )

    def _create_app(
        self, studio_id: str, teamspace_id: str, cluster_id: str, plugin_type: str, **other_arguments: Any
    ) -> Externalv1LightningappInstance:
        """Creates an arbitrary app."""
        body = AppsIdBody(cluster_id=cluster_id, plugin_arguments=other_arguments)

        resp = self._client.cloud_space_service_create_cloud_space_app_instance(
            body=body, project_id=teamspace_id, cloudspace_id=studio_id, id=plugin_type
        ).lightningappinstance

        if _LIGHTNING_DEBUG:
            print(f"Create App: {resp.id=} {teamspace_id=} {studio_id=} {cluster_id=}")

        return resp


@backoff.on_exception(backoff.expo, (requests.exceptions.HTTPError), max_tries=10)
def _upload_file_to_urls(*urls: V1PresignedUrl, path: str, progress_bar: bool = True) -> None:
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

    completed_uploads = []

    with open(path, "rb") as fd:
        reader_wrapper = CallbackIOWrapper(update_fn, fd, "read")

        for url in urls:
            # unfortunately we can't just pass the reader_wrapper directly since we only
            # need to read the first N bytes, finding a way to still pass the reader_wrapper
            # would likely be faster though
            data = reader_wrapper.read(_MAX_SIZE_MULTI_PART_CHUNK) if len(urls) > 1 else reader_wrapper

            response = requests.put(url.url, data=data)
            response.raise_for_status()

            etag = response.headers.get("ETag")
            completed_uploads.append(V1CompleteUpload(etag=etag, part_number=url.part_number))

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


class _FileUploader:
    """A class handling the upload to studios.

    Supports both single part and parallelized multi part uploads

    """

    def __init__(
        self,
        client: LightningClient,
        studio_id: str,
        teamspace_id: str,
        cluster_id: str,
        file_path: str,
        remote_path: str,
    ) -> None:
        self.client = client
        self.teamspace_id = teamspace_id
        self.cluster_id = cluster_id

        self.local_path = file_path

        self.remote_path = f"/cloudspaces/{studio_id}/code/content/{remote_path}"
        self.multipart_threshold = int(os.environ.get("LIGHTNING_MULTIPART_THRESHOLD", _MAX_SIZE_MULTI_PART_CHUNK))
        self.filesize = os.path.getsize(file_path)
        self.progress_bar = tqdm(
            desc=f"Uploading {os.path.split(file_path)[1]}",
            total=self.filesize,
            unit="B",
            unit_scale=True,
            unit_divisor=1000,
        )
        self.chunk_size = int(os.environ.get("LIGHTNING_MULTI_PART_PART_SIZE", _MAX_SIZE_MULTI_PART_CHUNK))
        assert self.chunk_size < _SIZE_LIMIT_SINGLE_PART
        self.max_workers = int(os.environ.get("LIGHTNING_MULTI_PART_MAX_WORKERS", _MAX_WORKERS))
        self.batch_size = int(os.environ.get("LIGHTNING_MULTI_PART_BATCH_SIZE", _MAX_BATCH_SIZE))

    def __call__(self) -> None:
        """Does the actual uploading.

        Dispatches to single and multipart uploads respectively

        """
        count = 1 if self.filesize <= self.multipart_threshold else math.ceil(self.filesize / self.chunk_size)

        if count == 1:
            return self._singlepart_upload()

        return self._multipart_upload(count=count)

    def _singlepart_upload(self) -> None:
        """Does a single part upload."""
        body = ProjectIdStorageBody(cluster_id=self.cluster_id, count=1, filename=self.remote_path)
        resp: V1UploadProjectArtifactResponse = self.client.lightningapp_instance_service_upload_project_artifact(
            body=body, project_id=self.teamspace_id
        )

        with open(self.local_path, "rb") as fd:
            reader_wrapper = CallbackIOWrapper(self.progress_bar.update, fd, "read")

            response = requests.put(resp.urls[0].url, data=reader_wrapper)
        response.raise_for_status()

        etag = response.headers.get("ETag")
        completed = [V1CompleteUpload(etag=etag, part_number=resp.urls[0].part_number)]

        completed_body = StorageCompleteBody(
            cluster_id=self.cluster_id, filename=self.remote_path, parts=completed, upload_id=resp.upload_id
        )
        self.client.lightningapp_instance_service_complete_upload_project_artifact(
            body=completed_body, project_id=self.teamspace_id
        )

    def _multipart_upload(self, count: int) -> None:
        """Does a parallel multipart upload."""
        body = ProjectIdStorageBody(cluster_id=self.cluster_id, count=count, filename=self.remote_path)
        resp: V1UploadProjectArtifactResponse = self.client.lightningapp_instance_service_upload_project_artifact(
            body=body, project_id=self.teamspace_id
        )

        # get indices for each batch, part numbers start at 1
        batched_indices = [
            list(range(i + 1, min(i + self.batch_size + 1, count + 1))) for i in range(0, count, self.batch_size)
        ]

        completed: List[V1CompleteUpload] = []
        with ThreadPoolExecutor(self.max_workers) as p:
            for batch in batched_indices:
                completed.extend(self._process_upload_batch(executor=p, batch=batch, upload_id=resp.upload_id))

        completed_body = StorageCompleteBody(
            cluster_id=self.cluster_id, filename=self.remote_path, parts=completed, upload_id=resp.upload_id
        )
        self.client.lightningapp_instance_service_complete_upload_project_artifact(
            body=completed_body, project_id=self.teamspace_id
        )

    def _process_upload_batch(self, executor: ThreadPoolExecutor, batch: List[int], upload_id: str) -> None:
        """Uploads a single batch of chunks in parallel."""
        urls = self._request_urls(parts=batch, upload_id=upload_id)
        func = partial(self._handle_uploading_single_part, upload_id=upload_id)
        return executor.map(func, urls)

    def _request_urls(self, parts: List[int], upload_id: str) -> List[V1PresignedUrl]:
        """Requests urls for a batch of parts."""
        body = UploadsUploadIdBody(cluster_id=self.cluster_id, filename=self.remote_path, parts=parts)
        resp: V1UploadProjectArtifactPartsResponse = (
            self.client.lightningapp_instance_service_upload_project_artifact_parts(body, self.teamspace_id, upload_id)
        )
        return resp.urls

    def _handle_uploading_single_part(self, presigned_url: V1PresignedUrl, upload_id: str) -> V1CompleteUpload:
        """Uploads a single part of a multipart upload including retires with backoff."""
        try:
            return self._handle_upload_presigned_url(
                presigned_url=presigned_url,
            )
        except Exception:
            return self._error_handling_upload(part=presigned_url.part_number, upload_id=upload_id)

    def _handle_upload_presigned_url(self, presigned_url: V1PresignedUrl) -> V1CompleteUpload:
        """Straightforward uploads the part given a single url."""
        with open(self.local_path, "rb") as f:
            f.seek(int(presigned_url.part_number) * self.chunk_size)
            data = f.read(self.chunk_size)

        response = requests.put(presigned_url.url, data=data)
        response.raise_for_status()
        self.progress_bar.update(self.chunk_size)

        etag = response.headers.get("ETag")
        return V1CompleteUpload(etag=etag, part_number=presigned_url.part_number)

    @backoff.on_exception(backoff.expo, (requests.exceptions.HTTPError), max_tries=10)
    def _error_handling_upload(self, part: int, upload_id: str) -> V1CompleteUpload:
        """Retries uploading with re-requesting the url."""
        urls = self._request_urls(
            parts=[part],
            upload_id=upload_id,
        )
        if len(urls) != 1:
            raise ValueError(
                f"expected to get exactly one url, but got {len(urls)} for part {part} of {self.remote_path}"
            )

        return self._handle_upload_presigned_url(presigned_url=urls[0])
