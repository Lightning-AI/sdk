import math
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Dict, List

import backoff
import requests
from tqdm import tqdm
from tqdm.utils import CallbackIOWrapper

from lightning_sdk.lightning_cloud.openapi import (
    ProjectIdStorageBody,
    StorageCompleteBody,
    UploadsUploadIdBody,
    V1CompleteUpload,
    V1PresignedUrl,
    V1UploadProjectArtifactPartsResponse,
    V1UploadProjectArtifactResponse,
)
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
        studio_id: str,
        teamspace_id: str,
        cluster_id: str,
        file_path: str,
        remote_path: str,
        progress_bar: bool,
    ) -> None:
        self.client = client
        self.teamspace_id = teamspace_id
        self.cluster_id = cluster_id

        self.local_path = file_path

        self.remote_path = (
            f"/cloudspaces/{studio_id}/code/content/{remote_path.replace('/teamspace/studios/this_studio/', '')}"
        )
        self.multipart_threshold = int(os.environ.get("LIGHTNING_MULTIPART_THRESHOLD", _MAX_SIZE_MULTI_PART_CHUNK))
        self.filesize = os.path.getsize(file_path)
        if progress_bar:
            self.progress_bar = tqdm(
                desc=f"Uploading {os.path.split(file_path)[1]}",
                total=self.filesize,
                unit="B",
                unit_scale=True,
                unit_divisor=1000,
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
            reader_wrapper = CallbackIOWrapper(
                self.progress_bar.update if self.progress_bar is not None else lambda x: None, fd, "read"
            )

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
            f.seek((int(presigned_url.part_number) - 1) * self.chunk_size)
            data = f.read(self.chunk_size)

        response = requests.put(presigned_url.url, data=data)
        response.raise_for_status()
        if self.progress_bar is not None:
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


class _DummyResponse:
    def __init__(self, data: bytes) -> None:
        self.data = data


# TODO: This should really come from some kind of metadata service
# TODO: Add trainium instances once feature flag is lifted
_MACHINE_TO_COMPUTE_NAME: Dict[Machine, str] = {
    Machine.CPU: "cpu-4",
    Machine.DATA_PREP: "data-large-3000",
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


def _get_cloud_url() -> str:
    cloud_url = os.environ.get("LIGHTNING_CLOUD_URL", _DEFAULT_CLOUD_URL)
    os.environ["LIGHTNING_CLOUD_URL"] = cloud_url
    return cloud_url
