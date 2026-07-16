import concurrent.futures
import errno
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache, partial
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Protocol, Tuple, TypedDict, Union, runtime_checkable

import backoff
import requests
from requests.exceptions import HTTPError
from tqdm.auto import tqdm

from lightning_sdk.constants import __GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__, _LIGHTNING_DEBUG
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi import (
    CloudSpaceServiceApi,
    CloudSpaceServiceCreateCloudSpaceAppInstanceBody,
    Externalv1LightningappInstance,
    ModelsStoreCompleteMultiPartUploadBody,
    ModelsStoreCreateMultiPartUploadBody,
    ModelsStoreGetModelFileUploadUrlsBody,
    V1CompletedPart,
    V1LoginRequest,
    V1PathMapping,
    V1SignedUrl,
)
from lightning_sdk.lightning_cloud.openapi.models.v1_model_version_archive import V1ModelVersionArchive
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.machine import Machine


@runtime_checkable
class Experiment(Protocol):
    id: str


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
# S3, R2, and GCS all cap multipart uploads at 10,000 parts
_MAX_UPLOAD_PARTS = 10000


def _local_file_matches_size(local_path: str, expected_size: Optional[int]) -> bool:
    """Return True if a local file exists and its size matches the expected size."""
    if expected_size is None:
        return False
    try:
        if not os.path.isfile(local_path):
            return False
        return os.path.getsize(local_path) == int(expected_size)
    except OSError:
        return False


class _IterableFileWrapper:
    """Workaround for requests 2.34.0 stream detection regression."""

    def __init__(self, wrapped: Any) -> None:
        self._wrapped = wrapped

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._wrapped)


class _BlobUploader:
    """Uploads a single file via the batch blob-upload endpoints.

    Requests presigned URL(s) from ``POST {endpoint_base}/blobs``, PUTs the bytes
    straight to storage (single-part below the multipart threshold, parallel
    multipart above it), then finalizes via ``POST {endpoint_base}/blobs/complete``
    where required: always for multipart, and for single-part only when
    ``notify_completion`` is set (the studio scope uses that so uploads show
    up in a running Studio).
    """

    def __init__(
        self,
        client: LightningClient,
        endpoint_base: str,
        file_path: str,
        remote_path: str,
        progress_bar: bool,
        cluster_id: Optional[str] = None,
        content_type: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        notify_completion: bool = False,
    ) -> None:
        """Initialise the uploader.

        Args:
            client: The Lightning API client, used for authentication.
            endpoint_base: Absolute URL of the upload scope, e.g.
                ``{host}/v1/projects/{id}/artifacts`` or
                ``{host}/v1/projects/{id}/artifacts/cloudspaces/{studio_id}``.
            file_path: Local path of the file to upload.
            remote_path: Destination blob path within the scope.
            progress_bar: Whether to show a tqdm progress bar during upload.
            cluster_id: Cluster to store the file on. Required for the project and
                uploads scopes, except for ``lightning_storage/`` paths; ignored by
                the studio scope.
            content_type: Optional content type to bind to the upload.
            extra_headers: Optional extra HTTP headers for the storage PUT requests.
            notify_completion: Whether to finalize single-part uploads too.
        """
        self.client = client
        self.endpoint_base = endpoint_base.rstrip("/")
        self.local_path = file_path
        self.remote_path = remote_path
        self.cluster_id = cluster_id
        self.content_type = content_type
        self.extra_headers = extra_headers
        self.notify_completion = notify_completion
        self.show_progress = progress_bar
        self.progress_bar = None

        self.filesize = os.path.getsize(file_path)
        self.multipart_threshold = int(os.environ.get("LIGHTNING_MULTIPART_THRESHOLD", _MAX_SIZE_MULTI_PART_CHUNK))
        self.chunk_size = int(os.environ.get("LIGHTNING_MULTI_PART_PART_SIZE", _MAX_SIZE_MULTI_PART_CHUNK))
        assert self.chunk_size < _SIZE_LIMIT_SINGLE_PART
        # storage providers cap multipart uploads at 10k parts; grow the chunks to fit
        if self.filesize > self.chunk_size * _MAX_UPLOAD_PARTS:
            self.chunk_size = math.ceil(self.filesize / _MAX_UPLOAD_PARTS)
        self.max_workers = int(os.environ.get("LIGHTNING_MULTI_PART_MAX_WORKERS", _MAX_WORKERS))
        self._token = _authenticate_and_get_token(client)

    def __call__(self) -> None:
        """Execute the upload, dispatching to single-part or multipart."""
        if self.filesize <= self.multipart_threshold:
            self._single_part_upload()
            if self.notify_completion:
                self._complete_upload()
            return

        count = math.ceil(self.filesize / self.chunk_size)
        upload_id, urls = self._create_multipart_upload(parts=count)
        if self.show_progress:
            self.progress_bar = tqdm(
                desc=f"Uploading {os.path.split(self.local_path)[1]}",
                total=self.filesize,
                unit="B",
                unit_scale=True,
                unit_divisor=1000,
                position=-1,
                mininterval=1,
            )
        with ThreadPoolExecutor(self.max_workers) as p:
            completed = list(p.map(partial(self._upload_part_with_recovery, upload_id=upload_id), urls))
        if self.progress_bar is not None:
            self.progress_bar.close()
        self._complete_upload(upload_id=upload_id, parts=completed)

    def _post_blob_request(self, suffix: str, blob: Dict[str, Any], action: str) -> requests.Response:
        """POST a one-blob batch to ``{endpoint_base}{suffix}``.

        Args:
            suffix: Route suffix, ``/blobs`` or ``/blobs/complete``.
            blob: The single entry of the request's ``blobs`` list.
            action: Verb for error messages, e.g. ``"request upload URLs for"``.

        Raises:
            HTTPError: On retryable statuses (5xx / 429), so backoff-wrapped
                callers retry.
            RuntimeError: On any other non-2xx status.
        """
        url = f"{self.endpoint_base}{suffix}"
        body: Dict[str, Any] = {"blobs": [blob]}
        if self.cluster_id:
            body["cluster_id"] = self.cluster_id
        r = requests.post(url, json=body, params={"token": self._token}, timeout=30)
        if r.status_code >= 500 or r.status_code == 429:
            raise HTTPError(
                f"Transient error trying to {action} '{self.remote_path}'. Status code: {r.status_code}", response=r
            )
        if r.status_code not in (200, 204):
            raise RuntimeError(f"Failed to {action} '{self.remote_path}'. Status code: {r.status_code}")
        return r

    def _create_upload(
        self, parts: int, part_numbers: Optional[List[int]] = None, upload_id: str = ""
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Request presigned upload URL(s) for the blob.

        Args:
            parts: Total number of parts (1 requests a single presigned PUT).
            part_numbers: With ``upload_id``, re-signs just these parts of an
                in-progress multipart upload instead of creating a new one.
            upload_id: The multipart upload to re-sign parts of.

        Returns:
            The upload ID (empty for single-part) and the URL descriptors, each
            with ``url`` and optional ``part_number``/``headers``.
        """
        blob: Dict[str, Any] = {"path": self.remote_path}
        if self.content_type:
            blob["content_type"] = self.content_type
        if upload_id:
            blob["upload_id"] = upload_id
            blob["part_numbers"] = part_numbers
        elif parts > 1:
            blob["parts"] = parts
            blob["part_size"] = self.chunk_size
        r = self._post_blob_request("/blobs", blob, action="request upload URLs for")
        result = r.json()["results"][0]
        return result.get("upload_id") or upload_id, result.get("urls") or []

    @backoff.on_exception(
        backoff.expo, (requests.exceptions.HTTPError, requests.exceptions.RequestException), max_tries=10
    )
    def _create_multipart_upload(self, parts: int) -> Tuple[str, List[Dict[str, Any]]]:
        """Create a multipart upload, retrying transient failures.

        Unlike single-part signing, creating a multipart upload makes the
        server reach out to storage, so it shares the transient failure modes
        of the storage requests themselves (e.g. a just-created
        lightning_storage folder's credentials may not have propagated yet).

        Returns:
            The upload ID and the URL descriptors for every part.
        """
        return self._create_upload(parts=parts)

    @backoff.on_exception(
        backoff.expo, (requests.exceptions.HTTPError, requests.exceptions.RequestException), max_tries=10
    )
    def _single_part_upload(self) -> None:
        """Request a presigned URL and PUT the whole file to it.

        Each retry requests a fresh URL, so an expired signature can't wedge the
        upload.

        Raises:
            RuntimeError: If the upload fails with a non-retryable status code.
        """
        _, urls = self._create_upload(parts=1)
        headers = dict(urls[0].get("headers") or {})
        if self.extra_headers:
            headers.update(self.extra_headers)

        with open(self.local_path, "rb") as f:
            if self.show_progress:
                with tqdm.wrapattr(
                    f,
                    "read",
                    desc=f"Uploading {os.path.split(self.local_path)[1]}",
                    total=self.filesize,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1000,
                ) as wrapped_file:
                    r = requests.put(
                        urls[0]["url"],
                        data=_IterableFileWrapper(wrapped_file),
                        timeout=30,
                        headers=headers or None,
                    )
            else:
                r = requests.put(urls[0]["url"], data=f, timeout=30, headers=headers or None)

        if r.status_code != 200:
            # Retry transient server errors / throttling, and also 401/403 from
            # storage: every attempt signs a fresh URL, which heals expired
            # signatures and newly issued storage credentials that haven't
            # propagated yet (e.g. right after a lightning_storage folder is
            # created). The backoff decorator only retries HTTPError/
            # RequestException, so raise an HTTPError for these instead of
            # failing immediately.
            if r.status_code >= 500 or r.status_code in (401, 403, 429):
                raise HTTPError(
                    f"Transient error uploading file '{self.local_path}'. Status code: {r.status_code}", response=r
                )
            raise RuntimeError(f"Failed to upload file '{self.local_path}'. Status code: {r.status_code}")

    def _upload_part_with_recovery(self, url_info: Dict[str, Any], upload_id: str) -> Dict[str, Any]:
        """Upload one part, falling back to re-signing its URL on failure.

        Args:
            url_info: URL descriptor with ``url`` and ``part_number``.
            upload_id: The multipart upload session ID, used to re-sign.

        Returns:
            The completed part as ``{"part_number": ..., "etag": ...}``.
        """
        try:
            return self._upload_part(url_info)
        except Exception:
            return self._resign_and_upload_part(part=int(url_info["part_number"]), upload_id=upload_id)

    def _upload_part(self, url_info: Dict[str, Any]) -> Dict[str, Any]:
        """PUT a single part to its presigned URL.

        Args:
            url_info: URL descriptor with ``url`` and ``part_number``.

        Returns:
            The completed part as ``{"part_number": ..., "etag": ...}``.
        """
        part_number = int(url_info["part_number"])
        with open(self.local_path, "rb") as f:
            f.seek((part_number - 1) * self.chunk_size)
            data = f.read(self.chunk_size)

        headers = dict(url_info.get("headers") or {})
        if self.extra_headers:
            headers.update(self.extra_headers)
        response = requests.put(url_info["url"], data=data, headers=headers or None)
        response.raise_for_status()
        if self.progress_bar is not None:
            self.progress_bar.update(len(data))

        return {"part_number": part_number, "etag": response.headers.get("ETag")}

    @backoff.on_exception(
        backoff.expo, (requests.exceptions.HTTPError, requests.exceptions.RequestException), max_tries=10
    )
    def _resign_and_upload_part(self, part: int, upload_id: str) -> Dict[str, Any]:
        """Re-sign a part's URL and retry uploading it.

        Args:
            part: The 1-based part number to retry.
            upload_id: The multipart upload session ID.

        Returns:
            The completed part as ``{"part_number": ..., "etag": ...}``.

        Raises:
            ValueError: If re-signing does not return exactly one URL.
        """
        _, urls = self._create_upload(parts=1, part_numbers=[part], upload_id=upload_id)
        if len(urls) != 1:
            raise ValueError(
                f"expected to get exactly one url, but got {len(urls)} for part {part} of {self.remote_path}"
            )
        return self._upload_part(urls[0])

    @backoff.on_exception(
        backoff.expo, (requests.exceptions.HTTPError, requests.exceptions.RequestException), max_tries=10
    )
    def _complete_upload(self, upload_id: str = "", parts: Optional[List[Dict[str, Any]]] = None) -> None:
        """Finalize the upload (multipart completion and/or Studio sync).

        Args:
            upload_id: The multipart upload session ID; empty for single-part.
            parts: The completed parts for a multipart upload.
        """
        blob: Dict[str, Any] = {"path": self.remote_path}
        if upload_id:
            blob["upload_id"] = upload_id
            blob["parts"] = parts
        self._post_blob_request("/blobs/complete", blob, action="finalize upload of")


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
        """Does a parallel multipart upload.

        Args:
            count: Total number of parts to split the file into.
        """
        body = ModelsStoreCreateMultiPartUploadBody(filepath=self.remote_path)
        resp = self.client.models_store_create_multi_part_upload(
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

        completed_body = ModelsStoreCompleteMultiPartUploadBody(filepath=self.remote_path, parts=completed)
        self.client.models_store_complete_multi_part_upload(
            completed_body,
            project_id=self.teamspace_id,
            model_id=self.model_id,
            version=self.version,
            upload_id=resp.upload_id,
        )

    def _process_upload_batch(self, executor: ThreadPoolExecutor, batch: List[int], upload_id: str) -> None:
        """Uploads a single batch of chunks in parallel.

        Args:
            executor: The thread-pool executor to submit upload tasks to.
            batch: List of 1-based part numbers in this batch.
            upload_id: The multipart upload session ID.
        """
        urls = self._request_urls(parts=batch, upload_id=upload_id)
        func = partial(self._handle_uploading_single_part, upload_id=upload_id)
        return executor.map(func, urls)

    def _request_urls(self, parts: List[int], upload_id: str) -> List[V1SignedUrl]:
        """Requests urls for a batch of parts.

        Args:
            parts: List of 1-based part numbers to request signed URLs for.
            upload_id: The multipart upload session ID.

        Returns:
            List[V1SignedUrl]: Signed URLs for each requested part.
        """
        body = ModelsStoreGetModelFileUploadUrlsBody(filepath=self.remote_path, parts=parts)
        resp = self.client.models_store_get_model_file_upload_urls(
            body,
            project_id=self.teamspace_id,
            model_id=self.model_id,
            version=self.version,
            upload_id=upload_id,
        )
        return resp.urls

    def _handle_uploading_single_part(self, presigned_url: V1SignedUrl, upload_id: str) -> V1CompletedPart:
        """Uploads a single part of a multipart upload including retires with backoff.

        Args:
            presigned_url: The signed URL and part metadata for this chunk.
            upload_id: The multipart upload session ID used for retry URL requests.

        Returns:
            V1CompletedPart: The ETag and part number for the completed upload.
        """
        try:
            return self._handle_upload_presigned_url(
                presigned_url=presigned_url,
            )
        except Exception:
            return self._error_handling_upload(part=presigned_url.part_number, upload_id=upload_id)

    def _handle_upload_presigned_url(self, presigned_url: V1SignedUrl) -> V1CompletedPart:
        """Straightforward uploads the part given a single url.

        Args:
            presigned_url: The signed URL and part metadata for this chunk.

        Returns:
            V1CompletedPart: The ETag and part number for the completed upload.
        """
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
        """Retries uploading with re-requesting the url.

        Args:
            part: The 1-based part number to retry.
            upload_id: The multipart upload session ID.

        Returns:
            V1CompletedPart: The ETag and part number for the completed upload.

        Raises:
            ValueError: If the re-requested URL list does not contain exactly one URL.
        """
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
        skip_if_exists: bool = True,
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
        self.skip_if_exists = skip_if_exists

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
        # Fast path: if size is already known and the local file matches, skip without hitting the API.
        if self.skip_if_exists and _local_file_matches_size(self.local_path, self._size):
            self.update_progress(self._size)
            return

        if self.url is None:
            self.refresh()

        # Re-check after refresh in case size was previously unknown (e.g. model files flow).
        if self.skip_if_exists and _local_file_matches_size(self.local_path, self._size):
            self.update_progress(self._size)
            return

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
    models = client.models_store_list_models(project_id=teamspace_id, name=name).models
    if not models:
        raise ValueError(f"Model `{name}` does not exist")
    elif len(models) > 1:
        raise ValueError("Multiple models with the same name found")
    if version is None or version == "default":
        return models[0].default_version
    versions = client.models_store_list_model_versions(project_id=teamspace_id, model_id=models[0].id).versions
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
    skip_if_exists: bool = True,
) -> List[str]:
    response = client.models_store_get_model_files(
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
        resp = client.models_store_get_model_file_url(
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
                skip_if_exists=skip_if_exists,
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
    skip_if_exists: bool = True,
) -> None:
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
        resp = client.storage_service_list_project_artifacts(
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
            response = client.storage_service_list_project_artifacts(
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
                    skip_if_exists=skip_if_exists,
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
    """Creates an arbitrary app.

    Args:
        client: The CloudSpace service API client.
        studio_id: The studio (cloudspace) ID to create the app in.
        teamspace_id: The teamspace (project) ID that owns the studio.
        cloud_account: The cloud account (cluster) ID for the app.
        plugin_type: The plugin type identifier for the app to create.
        **other_arguments: Additional plugin arguments forwarded to the request body.

    Returns:
        Externalv1LightningappInstance: The created app instance.
    """
    from lightning_sdk.utils.resolve import _LIGHTNING_SERVICE_EXECUTION_ID_KEY

    # Check if 'interruptible' is in the arguments and convert it to a string
    if isinstance(other_arguments, dict) and "interruptible" in other_arguments:
        other_arguments["spot"] = str(other_arguments["interruptible"]).lower()
        del other_arguments["interruptible"]

    body = CloudSpaceServiceCreateCloudSpaceAppInstanceBody(
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


def resolve_path_mappings(mappings: Dict[str, str]) -> List[V1PathMapping]:
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

    return path_mappings_list


class AccessibleResource(Enum):
    Studios = "studio"
    Drive = "drive"
    Jobs = "jobs"
    Deployments = "deployments"
    Pipelines = "pipelines"
    Models = "models"
    Containers = "containers"
    Settings = "settings"

    def __str__(self) -> str:
        """Return the string representation of the resource type.

        Returns:
            str: The string value of the resource type.
        """
        return self.value

    def __repr__(self) -> str:
        """Return the string representation of the resource type.

        Returns:
            str: The string value of the resource type.
        """
        return self.value

    def __eq__(self, other: object) -> bool:
        """Return True if the resource type is equal to the other resource type.

        Args:
            other: The object to compare against.

        Returns:
            bool: ``True`` if ``other`` represents the same resource type.
        """
        if isinstance(other, AccessibleResource):
            return self.value == other.value
        return str(other) == self.value

    def __hash__(self) -> int:
        """Return the hash of the resource type.

        Returns:
            int: Hash of the resource type's string value.
        """
        return hash(self.value)


@lru_cache
def allowed_resource_access(resource_type: AccessibleResource, teamspace_id: str) -> bool:
    # TODO: change this to proper API
    from lightning_sdk.api.teamspace_api import TeamspaceApi

    teamspace_api = TeamspaceApi()
    teamspace = teamspace_api._get_teamspace_by_id(teamspace_id=teamspace_id)

    # when we find the tab, check if it is enabled
    if teamspace.layout_config:
        for tab in teamspace.layout_config:
            if tab.slug == resource_type:
                return tab.is_enabled

    # tab isn't found, allow access by default for backwards compatibility
    # TODO: add additional checks here if required
    return True


def raise_access_error_if_not_allowed(resource_type: AccessibleResource, teamspace_id: str) -> None:
    if not allowed_resource_access(resource_type, teamspace_id):
        raise PermissionError(
            f"Access to {resource_type.name} has been disabled for this teamspace. "
            "Contact a teamspace administrator to enable it."
        )


def to_iso_z(dt: datetime) -> str:
    """Convert a datetime object to an ISO 8601 formatted string with UTC timezone (Z).

    This function takes a datetime object, converts it to UTC timezone, formats it
    to include milliseconds, and replaces the UTC offset with 'Z' to indicate UTC.

    Args:
        dt (datetime): The datetime object to be converted.

    Returns:
        str: The ISO 8601 formatted string in UTC timezone.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds")
    return dt.isoformat(timespec="milliseconds")


def _authenticate_and_get_token(client: Any) -> str:
    auth = Auth()
    auth.authenticate()
    return client.auth_service_login(V1LoginRequest(auth.api_key)).token
