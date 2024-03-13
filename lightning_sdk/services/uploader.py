import os
from concurrent.futures import ThreadPoolExecutor
from typing import List

import backoff
import requests
from tqdm import tqdm
from tqdm.utils import CallbackIOWrapper

from lightning_sdk.api.utils import (
    _MAX_BATCH_SIZE,
    _MAX_SIZE_MULTI_PART_CHUNK,
    _MAX_WORKERS,
    _SIZE_LIMIT_SINGLE_PART,
    _FileUploader,
)
from lightning_sdk.lightning_cloud.openapi import (
    IdCompleteBody,
    IdStorageBody,
    UploadsUploadIdBody,
    V1CompleteUpload,
    V1PresignedUrl,
    V1UploadProjectArtifactPartsResponse,
    V1UploadServiceExecutionArtifactResponse,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class _ServiceFileUploader(_FileUploader):
    """A class handling the upload to services.

    Supports both single part and parallelized multi part uploads

    """

    def __init__(
        self,
        client: LightningClient,
        teamspace_id: str,
        service_execution_id: str,
        upload_id: str,
        file_path: str,
        progress_bar: bool,
    ) -> None:
        self.client = client
        self.teamspace_id = teamspace_id
        self.service_execution_id = service_execution_id
        self.upload_id = upload_id
        self.local_path = file_path
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

    @backoff.on_exception(backoff.expo, (requests.exceptions.HTTPError), max_tries=10)
    def _singlepart_upload(self) -> None:
        """Does a single part upload."""
        body = IdStorageBody(argument_upload_id=self.upload_id, count=1)
        resp: V1UploadServiceExecutionArtifactResponse = self.client.endpoint_service_upload_service_execution_artifact(
            body=body, project_id=self.teamspace_id, id=self.service_execution_id
        )

        with open(self.local_path, "rb") as fd:
            reader_wrapper = CallbackIOWrapper(
                self.progress_bar.update if self.progress_bar is not None else lambda x: None, fd, "read"
            )

            response = requests.put(resp.urls[0].url, data=reader_wrapper)
        response.raise_for_status()

        etag = response.headers.get("ETag")
        completed = [V1CompleteUpload(etag=etag, part_number=resp.urls[0].part_number)]

        completed_body = IdCompleteBody(argument_upload_id=self.upload_id, parts=completed, upload_id=resp.upload_id)
        self.client.endpoint_service_complete_upload_service_execution_artifact(
            body=completed_body,
            project_id=self.teamspace_id,
            id=self.service_execution_id,
        )

    def _multipart_upload(self, count: int) -> None:
        """Does a parallel multipart upload."""
        body = IdStorageBody(upload_id=self.upload_id, count=count)
        resp: V1UploadServiceExecutionArtifactResponse = self.client.endpoint_service_upload_service_execution_artifact(
            body=body, project_id=self.teamspace_id, id=self.service_execution_id
        )

        # get indices for each batch, part numbers start at 1
        batched_indices = [
            list(range(i + 1, min(i + self.batch_size + 1, count + 1))) for i in range(0, count, self.batch_size)
        ]

        completed: List[V1CompleteUpload] = []
        with ThreadPoolExecutor(self.max_workers) as p:
            for batch in batched_indices:
                completed.extend(self._process_upload_batch(executor=p, batch=batch, upload_id=resp.upload_id))

        completed_body = IdCompleteBody(
            cluster_id=self.cluster_id, filename=self.remote_path, parts=completed, upload_id=resp.upload_id
        )
        self.client.lightningapp_instance_service_complete_upload_project_artifact(
            body=completed_body, project_id=self.teamspace_id
        )

    def _request_urls(self, parts: List[int], upload_id: str) -> List[V1PresignedUrl]:
        """Requests urls for a batch of parts."""
        body = UploadsUploadIdBody(cluster_id=self.cluster_id, filename=self.remote_path, parts=parts)
        resp: V1UploadProjectArtifactPartsResponse = (
            self.client.lightningapp_instance_service_upload_project_artifact_parts(body, self.teamspace_id, upload_id)
        )
        return resp.urls
