import concurrent.futures
import errno
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict, Union

import backoff
import requests
from tqdm.auto import tqdm

from lightning_sdk.constants import __GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__, _LIGHTNING_DEBUG
from lightning_sdk.lightning_cloud.openapi import (
    CloudSpaceServiceApi,
    Externalv1LightningappInstance,
    ModelsStoreApi,
    ProjectIdStorageBody,
    StorageCompleteBody,
    StorageServiceApi,
    UploadIdCompleteBody,
    UploadIdPartsBody,
    V1CompletedPart,
    V1CompleteUpload,
    V1PathMapping,
    V1PresignedUrl,
    V1SignedUrl,
    V1UploadProjectArtifactPartsResponse,
    V1UploadProjectArtifactResponse,
    VersionUploadsBody,
)
from lightning_sdk.lightning_cloud.openapi.models.v1_model_version_archive import V1ModelVersionArchive

try:
    from lightning_sdk.lightning_cloud.openapi import AppsIdBody1 as AppsIdBody
except ImportError:
    from lightning_sdk.lightning_cloud.openapi import AppsIdBody

try:
    from lightning_sdk.lightning_cloud.openapi import UploadsUploadIdBody1 as UploadsUploadIdBody
except ImportError:
    from lightning_sdk.lightning_cloud.openapi import UploadsUploadIdBody

from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.machine import Machine


class _DummyBody:
    def __init__(self) -> None:
        self.swagger_types = {}
        self.attribute_map = {}


_BYTES_PER_KB = 1000
_BYTES_PER_MB = 1000 * _BYTES_PER_KB
_BYTES_PER_GB = 1000 * _BYTES_PER_MB

_SIZE_LIMIT_SINGLE_PART = 5 * _BYTES_PER_GB
_MAX_SIZE_MULTI_PART_CHUNK = 100 * _BYTES_PER_MB
_MAX_BATCH_SIZE = 50
_MAX_WORKERS = 10


class _FileUploader:
    """A class handling the upload to studios.

    Supports both single part and parallelized multi part uploads

    """

    def __init__(
        self,
        client: LightningClient,
        teamspace_id: str,
        cloud_account: str,
        file_path: str,
        remote_path: str,
        progress_bar: bool,
    ) -> None:
        self.client = client
        self.teamspace_id = teamspace_id
        self.cloud_account = cloud_account

        self.local_path = file_path

        self.remote_path = remote_path
        self.multipart_threshold = int(os.environ.get("LIGHTNING_MULTIPART_THRESHOLD", _MAX_SIZE_MULTI_PART_CHUNK))
        self.filesize = os.path.getsize(file_path)
        if progress_bar:
            self.progress_bar = tqdm(
                desc=f"Uploading {os.path.split(file_path)[1]}",
                total=self.filesize,
                unit="B",
                unit_scale=True,
                unit_divisor=1000,
                position=-1,
                mininterval=1,
            )
        else:
            self.progress_bar = None
        self.chunk_size = int(os.environ.get("LIGHTNING_MULTI_PART_PART_SIZE", _MAX_SIZE_MULTI_PART_CHUNK))
        assert self.chunk_size < _SIZE_LIMIT_SINGLE_PART
        self.max_workers = int(os.environ.get("LIGHTNING_MULTI_PART_MAX_WORKERS", _MAX_WORKERS))
        self.batch_size = int(os.environ.get("LIGHTNING_MULTI_PART_BATCH_SIZE", _MAX_BATCH_SIZE))

    def __call__(self) -> None:
        """Does the actual uploading.

        Dispatches to single and multipart uploads respectively

        """
        count = 1 if self.filesize <= self.multipart_threshold else math.ceil(self.filesize / self.chunk_size)

        return self._multipart_upload(count=count)

    def _multipart_upload(self, count: int) -> None:
        """Does a parallel multipart upload."""
        body = ProjectIdStorageBody(cluster_id=self.cloud_account, filename=self.remote_path)
        resp: V1UploadProjectArtifactResponse = self.client.storage_service_upload_project_artifact(
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
            cluster_id=self.cloud_account, filename=self.remote_path, parts=completed, upload_id=resp.upload_id
        )
        self.client.storage_service_complete_upload_project_artifact(body=completed_body, project_id=self.teamspace_id)

    def _process_upload_batch(self, executor: ThreadPoolExecutor, batch: List[int], upload_id: str) -> None:
        """Uploads a single batch of chunks in parallel."""
        urls = self._request_urls(parts=batch, upload_id=upload_id)
        func = partial(self._handle_uploading_single_part, upload_id=upload_id)
        return executor.map(func, urls)

    def _request_urls(self, parts: List[int], upload_id: str) -> List[V1PresignedUrl]:
        """Requests urls for a batch of parts."""
        body = UploadsUploadIdBody(filename=self.remote_path, parts=parts, cluster_id=self.cloud_account)
        resp: V1UploadProjectArtifactPartsResponse = self.client.storage_service_upload_project_artifact_parts(
            body, self.teamspace_id, upload_id
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
            f.seek((int(presigned_url.part_number) - 1) * self.chunk_size)
            data = f.read(self.chunk_size)

        response = requests.put(presigned_url.url, data=data)
        response.raise_for_status()
        if self.progress_bar is not None:
            self.progress_bar.update(len(data))

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


class _ModelFileUploader:
    """A class handling the upload of model artifacts.

    Supports parallelized multi-part uploads.

    """

    def __init__(
        self,
        client: LightningClient,
        model_id: str,
        version: str,
        teamspace_id: str,
        file_path: str,
        remote_path: str,
        progress_bar: bool,
    ) -> None:
        self.client = client
        self.model_id = model_id
        self.version = version
        self.teamspace_id = teamspace_id
        self.local_path = file_path
        self.remote_path = remote_path

        self.api = ModelsStoreApi(client.api_client)
        self.multipart_threshold = int(os.environ.get("LIGHTNING_MULTIPART_THRESHOLD", _MAX_SIZE_MULTI_PART_CHUNK))
        self.filesize = os.path.getsize(file_path)
        if progress_bar:
            self.progress_bar = tqdm(
                desc=f"Uploading {os.path.split(file_path)[1]}",
                total=self.filesize,
                unit="B",
                unit_scale=True,
                unit_divisor=1000,
                leave=False,
                position=-1,
                mininterval=1,
            )
        else:
            self.progress_bar = None
        self.chunk_size = int(os.environ.get("LIGHTNING_MULTI_PART_PART_SIZE", _MAX_SIZE_MULTI_PART_CHUNK))
        assert self.chunk_size < _SIZE_LIMIT_SINGLE_PART
        self.max_workers = int(os.environ.get("LIGHTNING_MULTI_PART_MAX_WORKERS", _MAX_WORKERS))
        self.batch_size = int(os.environ.get("LIGHTNING_MULTI_PART_BATCH_SIZE", _MAX_BATCH_SIZE))

    def __call__(self) -> None:
        """Does the actual uploading."""
        count = 1 if self.filesize <= self.multipart_threshold else math.ceil(self.filesize / self.chunk_size)
        return self._multipart_upload(count=count)

    def _multipart_upload(self, count: int) -> None:
        """Does a parallel multipart upload."""
        body = VersionUploadsBody(filepath=self.remote_path)
        resp = self.api.models_store_create_multi_part_upload(
            body,
            project_id=self.teamspace_id,
            model_id=self.model_id,
            version=self.version,
        )

        # get indices for each batch, part numbers start at 1
        batched_indices = [
            list(range(i + 1, min(i + self.batch_size + 1, count + 1))) for i in range(0, count, self.batch_size)
        ]

        completed: List[V1CompletedPart] = []
        with ThreadPoolExecutor(self.max_workers) as p:
            for batch in batched_indices:
                completed.extend(self._process_upload_batch(executor=p, batch=batch, upload_id=resp.upload_id))

        completed_body = UploadIdCompleteBody(filepath=self.remote_path, parts=completed)
        self.api.models_store_complete_multi_part_upload(
            completed_body,
            project_id=self.teamspace_id,
            model_id=self.model_id,
            version=self.version,
            upload_id=resp.upload_id,
        )

    def _process_upload_batch(self, executor: ThreadPoolExecutor, batch: List[int], upload_id: str) -> None:
        """Uploads a single batch of chunks in parallel."""
        urls = self._request_urls(parts=batch, upload_id=upload_id)
        func = partial(self._handle_uploading_single_part, upload_id=upload_id)
        return executor.map(func, urls)

    def _request_urls(self, parts: List[int], upload_id: str) -> List[V1SignedUrl]:
        """Requests urls for a batch of parts."""
        body = UploadIdPartsBody(filepath=self.remote_path, parts=parts)
        resp = self.api.models_store_get_model_file_upload_urls(
            body,
            project_id=self.teamspace_id,
            model_id=self.model_id,
            version=self.version,
            upload_id=upload_id,
        )
        return resp.urls

    def _handle_uploading_single_part(self, presigned_url: V1SignedUrl, upload_id: str) -> V1CompletedPart:
        """Uploads a single part of a multipart upload including retires with backoff."""
        try:
            return self._handle_upload_presigned_url(
                presigned_url=presigned_url,
            )
        except Exception:
            return self._error_handling_upload(part=presigned_url.part_number, upload_id=upload_id)

    def _handle_upload_presigned_url(self, presigned_url: V1SignedUrl) -> V1CompletedPart:
        """Straightforward uploads the part given a single url."""
        with open(self.local_path, "rb") as f:
            f.seek((int(presigned_url.part_number) - 1) * self.chunk_size)
            data = f.read(self.chunk_size)

        response = requests.put(presigned_url.url, data=data)
        response.raise_for_status()
        if self.progress_bar is not None:
            self.progress_bar.update(len(data))

        etag = response.headers.get("ETag")
        return V1CompletedPart(etag=etag, part_number=presigned_url.part_number)

    @backoff.on_exception(backoff.expo, (requests.exceptions.HTTPError), max_tries=10)
    def _error_handling_upload(self, part: int, upload_id: str) -> V1CompletedPart:
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


class _DummyResponse:
    def __init__(self, data: bytes) -> None:
        self.data = data


def _machine_to_compute_name(machine: Union[Machine, str]) -> str:
    if isinstance(machine, Machine):
        if machine.instance_type is not None:
            return machine.instance_type
        return machine.slug
    return machine


_DEFAULT_CLOUD_URL = "https://lightning.ai"
_DEFAULT_REGISTRY_URL = "litcr.io"


def _get_cloud_url() -> str:
    cloud_url = os.environ.get("LIGHTNING_CLOUD_URL", _DEFAULT_CLOUD_URL)
    os.environ["LIGHTNING_CLOUD_URL"] = cloud_url
    return cloud_url


def _get_registry_url() -> str:
    registry_url = os.environ.get("LIGHTNING_REGISTRY_URL", _DEFAULT_REGISTRY_URL)
    os.environ["LIGHTNING_REGISTRY_URL"] = registry_url
    return registry_url


def _sanitize_studio_remote_path(path: str, studio_id: str) -> str:
    path = path.replace("/teamspace/studios/this_studio/", "")
    root = f"/cloudspaces/{studio_id}/code/content/"
    return os.path.join(root, path)


def _resolve_teamspace_remote_path(path: str) -> str:
    return f"/Uploads/{path.replace('/teamspace/studios/this_studio/', '')}"


_DOWNLOAD_REQUEST_CHUNK_SIZE = 10 * _BYTES_PER_MB
_DOWNLOAD_MIN_CHUNK_SIZE = 100 * _BYTES_PER_KB


class _RefreshResponse(TypedDict):
    url: str
    size: int


class _FileDownloader:
    def __init__(
        self,
        teamspace_id: str,
        remote_path: str,
        file_path: str,
        executor: ThreadPoolExecutor,
        num_workers: int = 20,
        progress_bar: Optional[tqdm] = None,
        url: Optional[str] = None,
        size: Optional[int] = None,
        refresh_fn: Optional[Callable[[], _RefreshResponse]] = None,
    ) -> None:
        self.teamspace_id = teamspace_id
        self.local_path = file_path
        self.remote_path = remote_path
        self.progress_bar = progress_bar
        self.num_workers = num_workers
        self._url = url
        self._size = size
        self.executor = executor
        self.refresh_fn = refresh_fn

    @backoff.on_exception(backoff.expo, ApiException, max_tries=10)
    def refresh(self) -> None:
        if self.refresh_fn is not None:
            response = self.refresh_fn()
            self._url = response["url"]
            self._size = response["size"]

    @property
    def url(self) -> str:
        return self._url

    @property
    def size(self) -> int:
        return self._size

    def update_progress(self, n: int) -> None:
        if self.progress_bar is None:
            return
        self.progress_bar.update(n)

    def update_filename(self, desc: str) -> None:
        if self.progress_bar is None:
            return
        self.progress_bar.set_description(f"{(desc[:72] + '...') if len(desc) > 75 else desc:<75.75}")

    @backoff.on_exception(backoff.expo, (requests.exceptions.HTTPError), max_tries=10)
    def _download_chunk(self, filename: str, start_end: Tuple[int]) -> None:
        start, end = start_end
        headers = {"Range": f"bytes={start}-{end}"}

        with requests.get(self.url, headers=headers, stream=True) as response:
            if response.status_code in [200, 206]:
                with open(filename, "r+b") as f:
                    f.seek(start)
                    for chunk in response.iter_content(chunk_size=_DOWNLOAD_REQUEST_CHUNK_SIZE):
                        f.write(chunk)
                        self.update_progress(len(chunk))  # tqdm write is thread-safe
            if response.status_code == 403:  # Expired
                self.refresh()
            response.raise_for_status()

    def _create_empty_file(self, filename: str, file_size: int) -> None:
        if hasattr(os, "posix_fallocate"):
            fd = os.open(filename, os.O_RDWR | os.O_CREAT)
            if file_size > 0:
                os.posix_fallocate(fd, 0, file_size)
            os.close(fd)
        else:
            with open(filename, "wb") as f:
                block_size = 1024 * 1024
                for _ in range(file_size // block_size):
                    f.write(b"\x00" * block_size)

                remaining_size = file_size % block_size

                if remaining_size > 0:
                    f.write(b"\x00" * remaining_size)

    def _multipart_download(self, filename: str, num_workers: int) -> None:
        self.update_filename(f"Downloading {self.remote_path}")

        num_chunks = num_workers
        chunk_size = math.ceil(self.size / num_chunks)

        if chunk_size < _DOWNLOAD_MIN_CHUNK_SIZE:
            num_chunks = math.ceil(self.size / _DOWNLOAD_MIN_CHUNK_SIZE)
            chunk_size = _DOWNLOAD_MIN_CHUNK_SIZE

        ranges = []
        for part_number in range(num_chunks):
            start = part_number * chunk_size
            end = min(start + chunk_size - 1, self.size - 1)
            ranges.append((start, end))

        futures = [self.executor.submit(self._download_chunk, filename, r) for r in ranges]
        concurrent.futures.wait(futures)

    def download(self) -> None:
        if self.url is None:
            self.refresh()

        tmp_filename = f"{self.local_path}.download"

        try:
            self._create_empty_file(tmp_filename, self.size)
        except OSError as e:
            if e.errno == errno.ENOSPC:
                print(f"Tried to create {self.local_path} of size {self.size}, but no space left on device.")
            else:
                print(f"An error occurred while creating file {self.local_path}: {e}.")

            os.remove(tmp_filename)
            raise

        if self.size == 0:
            os.rename(tmp_filename, self.local_path)
            return

        try:
            self._multipart_download(tmp_filename, self.num_workers)
        except Exception as e:
            print(f"An error occurred while downloading file {self.remote_path}: {e}.")

            os.remove(tmp_filename)
            raise

        os.rename(tmp_filename, self.local_path)


def _get_model_version(client: LightningClient, teamspace_id: str, name: str, version: str) -> V1ModelVersionArchive:
    api = ModelsStoreApi(client.api_client)
    models = api.models_store_list_models(project_id=teamspace_id, name=name).models
    if not models:
        raise ValueError(f"Model `{name}` does not exist")
    elif len(models) > 1:
        raise ValueError("Multiple models with the same name found")
    if version is None or version == "default":
        return models[0].default_version
    versions = api.models_store_list_model_versions(project_id=teamspace_id, model_id=models[0].id).versions
    if not versions:
        raise ValueError(f"Model `{name}` does not have any versions")
    for ver in versions:
        if ver.version == version:
            return ver
    raise ValueError(f"Model `{name}` does not have version `{version}`")


def _download_model_files(
    client: LightningClient,
    teamspace_name: str,
    teamspace_owner_name: str,
    name: str,
    version: str,
    download_dir: Path,
    progress_bar: bool,
    num_workers: int = 20,
) -> List[str]:
    api = ModelsStoreApi(client.api_client)
    response = api.models_store_get_model_files(
        project_name=teamspace_name, project_owner_name=teamspace_owner_name, name=name, version=version
    )

    pbar = None
    if progress_bar:
        pbar = tqdm(
            desc=f"Downloading {version}",
            unit="B",
            total=float(response.size_bytes),
            unit_scale=True,
            unit_divisor=1000,
            position=-1,
            mininterval=1,
        )

    def refresh_fn(filename: str) -> _RefreshResponse:
        resp = api.models_store_get_model_file_url(
            project_id=response.project_id,
            model_id=response.model_id,
            version=response.version,
            filepath=filename,
        )
        return {"url": resp.url, "size": int(resp.size)}

    with ThreadPoolExecutor(max_workers=min(num_workers, len(response.filepaths))) as file_executor, ThreadPoolExecutor(
        max_workers=num_workers
    ) as part_executor:
        futures = []

        for filepath in response.filepaths:
            local_file = download_dir / filepath
            local_file.parent.mkdir(parents=True, exist_ok=True)

            file_downloader = _FileDownloader(
                teamspace_id=response.project_id,
                remote_path=filepath,
                file_path=str(local_file),
                num_workers=num_workers,
                progress_bar=pbar,
                executor=part_executor,
                refresh_fn=lambda f=filepath: refresh_fn(f),
            )

            futures.append(file_executor.submit(file_downloader.download))

        # wait for all threads
        concurrent.futures.wait(futures)

        return response.filepaths


def _download_teamspace_files(
    client: LightningClient,
    teamspace_id: str,
    cluster_id: str,
    prefix: str,
    download_dir: Path,
    progress_bar: bool,
    num_workers: int = os.cpu_count() * 4,
) -> None:
    api = StorageServiceApi(client.api_client)
    response = None

    pbar = None
    if progress_bar:
        pbar = tqdm(
            desc="Downloading files",
            unit="B",
            unit_scale=True,
            unit_divisor=1000,
            position=-1,
            mininterval=1,
        )

    def refresh_fn(filename: str) -> _RefreshResponse:
        resp = api.storage_service_list_project_artifacts(
            project_id=teamspace_id,
            cluster_id=cluster_id,
            page_token="",
            include_download_url=True,
            prefix=prefix + filename,
            page_size=1,
        )
        return {"url": resp.artifacts[0].url, "size": int(resp.artifacts[0].size_bytes)}

    with ThreadPoolExecutor(max_workers=num_workers) as file_executor, ThreadPoolExecutor(
        max_workers=num_workers
    ) as part_executor:
        while response is None or (response is not None and response.next_page_token != ""):
            response = api.storage_service_list_project_artifacts(
                project_id=teamspace_id,
                cluster_id=cluster_id,
                page_token=response.next_page_token if response is not None else "",
                include_download_url=True,
                prefix=prefix,
                page_size=1000,
            )

            page_futures = []
            for file in response.artifacts:
                local_file = download_dir / file.filename
                local_file.parent.mkdir(parents=True, exist_ok=True)

                file_downloader = _FileDownloader(
                    teamspace_id=teamspace_id,
                    remote_path=file.filename,
                    file_path=str(local_file),
                    num_workers=num_workers,
                    progress_bar=pbar,
                    executor=part_executor,
                    url=file.url,
                    size=int(file.size_bytes),
                    refresh_fn=lambda f=file: refresh_fn(f.filename),
                )

                page_futures.append(file_executor.submit(file_downloader.download))

            if page_futures:
                concurrent.futures.wait(page_futures)

            pbar.set_description("Download complete")


def _create_app(
    client: CloudSpaceServiceApi,
    studio_id: str,
    teamspace_id: str,
    cloud_account: str,
    plugin_type: str,
    **other_arguments: Any,
) -> Externalv1LightningappInstance:
    """Creates an arbitrary app."""
    from lightning_sdk.utils.resolve import _LIGHTNING_SERVICE_EXECUTION_ID_KEY

    # Check if 'interruptible' is in the arguments and convert it to a string
    if isinstance(other_arguments, dict) and "interruptible" in other_arguments:
        other_arguments["spot"] = str(other_arguments["interruptible"]).lower()
        del other_arguments["interruptible"]

    body = AppsIdBody(
        cluster_id=cloud_account,
        plugin_arguments=other_arguments,
        service_id=os.getenv(_LIGHTNING_SERVICE_EXECUTION_ID_KEY),
        unique_id=__GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__[studio_id],
    )

    resp = client.cloud_space_service_create_cloud_space_app_instance(
        body=body, project_id=teamspace_id, cloudspace_id=studio_id, id=plugin_type
    ).lightningappinstance

    if _LIGHTNING_DEBUG:
        print(f"Create App: {resp.id=} {teamspace_id=} {studio_id=} {cloud_account=}")

    return resp


def remove_datetime_prefix(text: str) -> str:
    # Use a regular expression to match the datetime pattern at the start of each line
    # lines looks something like
    # '[2025-01-08T14:15:03.797142418Z] ⚡  ~ echo Hello\n[2025-01-08T14:15:03.803077717Z] Hello\n'
    return re.sub(r"^\[.*?\] ", "", text, flags=re.MULTILINE)


def resolve_path_mappings(
    mappings: Dict[str, str],
    artifacts_local: Optional[str],
    artifacts_remote: Optional[str],
) -> List[V1PathMapping]:
    path_mappings_list = []
    for k, v in mappings.items():
        splitted = str(v).rsplit(":", 1)
        connection_name: str
        connection_path: str
        if len(splitted) == 1:
            connection_name = splitted[0]
            connection_path = ""
        else:
            connection_name, connection_path = splitted

        path_mappings_list.append(
            V1PathMapping(
                connection_name=connection_name,
                connection_path=connection_path,
                container_path=k,
            )
        )

    if artifacts_remote:
        splitted = str(artifacts_remote).rsplit(":", 2)
        if len(splitted) not in (2, 3):
            raise RuntimeError(
                f"Artifacts remote need to be of format efs:connection_name[:path] but got {artifacts_remote}"
            )
        else:
            if not artifacts_local:
                raise RuntimeError("If Artifacts remote is specified, artifacts local should be specified as well")

            if len(splitted) == 2:
                _, connection_name = splitted
                connection_path = ""
            else:
                _, connection_name, connection_path = splitted

            path_mappings_list.append(
                V1PathMapping(
                    connection_name=connection_name,
                    connection_path=connection_path,
                    container_path=artifacts_local,
                )
            )

    return path_mappings_list
