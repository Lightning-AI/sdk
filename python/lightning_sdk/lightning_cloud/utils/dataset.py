from typing import List, Optional, Union
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

import backoff
import requests
from tqdm.auto import tqdm

from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.lightning_cloud.openapi.api_client import ApiClient
from lightning_sdk.lightning_cloud import env

from lightning_sdk.api.utils import (
    _BYTES_PER_MB,
    _MAX_BATCH_SIZE,
    _MAX_SIZE_MULTI_PART_CHUNK,
    _MAX_WORKERS,
    _SIZE_LIMIT_SINGLE_PART,
)

# Total upload concurrency budget, split across files x within-file parts.
_DEFAULT_UPLOAD_WORKERS = 16


def _parse_dataset_path(name: str) -> tuple:
    """Parse a dataset path like 'org/teamspace/dataset/version' into components.

    Returns (org, teamspace_name, dataset_name, version).
    """
    parts = name.split("/")
    if len(parts) == 3:
        # org/teamspace/dataset_name (no version specified)
        org_name, ts_name, dataset_name = parts
        version = None
    elif len(parts) >= 4:
        # org/teamspace/dataset_name/version
        org_name, ts_name, dataset_name, *rest = parts
        version = rest[0] if rest else None
    else:
        raise ValueError(
            "NAME must be a Lightning path in the format <ORG>/<TEAMSPACE>/<DATASET_NAME> "
            "or <ORG>/<TEAMSPACE>/<DATASET_NAME>/<VERSION>, "
            "e.g. 'my-org/my-teamspace/my-dataset' or 'my-org/my-teamspace/my-dataset/v3'"
        )
    if not org_name or not ts_name or not dataset_name:
        raise ValueError(
            "NAME must be a Lightning path in the format <ORG>/<TEAMSPACE>/<DATASET_NAME> "
            "or <ORG>/<TEAMSPACE>/<DATASET_NAME>/<VERSION>, "
            "e.g. 'my-org/my-teamspace/my-dataset' or 'my-org/my-teamspace/my-dataset/v3'"
        )
    return org_name, ts_name, dataset_name, version


def _resolve_dataset_current_version(project_id: str, dataset_name: str) -> Optional[str]:
    """Resolve a dataset name to its current version.

    If no current version exists, returns None.
    Raises ValueError if the dataset cannot be found.
    """
    client = LightningClient(retry=False)

    api_client: ApiClient = client.api_client
    url = env.LIGHTNING_CLOUD_URL
    resp = api_client.request(
        "GET",
        f"{url}/v1/projects/{project_id}/lit-datasets",
        headers=api_client.default_headers,
        _preload_content=True,
    )
    data = json.loads(resp.data) if resp.data else {}
    for ds in data.get("datasets", []):
        if ds.get("name") == dataset_name:
            current_version = None
            default_ver = ds.get("default_version") or ds.get("defaultVersion")
            if default_ver and default_ver.get("version"):
                current_version = default_ver["version"]
            if not current_version:
                latest_ver = ds.get("latest_version") or ds.get("latestVersion")
                if latest_ver and latest_ver.get("version"):
                    current_version = latest_ver["version"]
            if not current_version:
                current_version = ds.get("version")
            return current_version

    raise ValueError(f"Dataset '{dataset_name}' not found in project '{project_id}'.")


def _resolve_dataset_version(project_id: str, dataset_name: str, version: Optional[str] = None) -> str:
    """Resolve the dataset version, defaulting to the most recent if not provided.

    Args:
        project_id: The project ID.
        dataset_name: The dataset ID (name).
        version: Optional version. If None, the most recent version is returned.

    Returns:
        The resolved version string.

    Raises:
        ValueError: If the dataset cannot be found or has no version.
    """
    if version:
        return version

    current_version = _resolve_dataset_current_version(project_id, dataset_name)
    if current_version:
        return current_version

    raise ValueError(f"Dataset '{dataset_name}' not found in project '{project_id}', or it has no versions.")


def _download_dataset_version(
    project_id: str,
    dataset_name: str,
    version: str,
    target_path: str,
    cluster_id: Optional[str] = None,
):
    """
    Download a dataset version as a zip file from the API.

    Fetches presigned file URLs from the files endpoint, downloads each file,
    and packages them into a proper zip archive at the target path.

    Args:
        project_id: The project ID.
        dataset_name: The dataset name.
        version: The dataset version to download.
        target_path: Local file path where the downloaded zip will be saved.
        cluster_id: Optional cluster ID.
    """
    import shutil
    import tempfile
    import urllib.request

    cloud_url = env.LIGHTNING_CLOUD_URL
    client = LightningClient(retry=False)
    api_client: ApiClient = client.api_client

    resolved_id = dataset_name
    try:
        resp = api_client.request(
            "GET",
            f"{cloud_url}/v1/projects/{project_id}/lit-datasets",
            headers=api_client.default_headers,
            _preload_content=True,
        )
        data = json.loads(resp.data) if resp.data else {}
        for ds in data.get("datasets", []):
            if ds.get("name") == dataset_name:
                resolved_id = ds.get("id", dataset_name)
                break
    except Exception:
        pass

    # get presigned file URLs
    files_url = f"{cloud_url}/v1/projects/{project_id}/lit-datasets/{resolved_id}/versions/{version}/files"
    query_params = {}
    if cluster_id:
        query_params["clusterId"] = cluster_id

    resp = api_client.request(
        "GET",
        files_url,
        query_params=query_params,
        headers=api_client.default_headers,
        _preload_content=True,
    )

    try:
        files_data = json.loads(resp.data) if resp.data else {}
    except json.JSONDecodeError:
        raise ValueError(f"Failed to parse response from {files_url}: {resp.data[:200]}")

    files_list = files_data.get("files", [])
    if not files_list:
        raise ValueError(f"No files found for dataset '{dataset_name}' version '{version}' in project '{project_id}'.")

    # create a zip archive from the downloaded files
    tmp_dir = tempfile.mkdtemp()
    try:
        for i, file_info in enumerate(files_list):
            file_url = file_info.get("url")
            if not file_url:
                continue
            filepath = file_info.get("filepath", f"file_{i}")
            filepath = filepath.lstrip("/")
            local_tmp = os.path.join(tmp_dir, filepath)
            os.makedirs(os.path.dirname(local_tmp), exist_ok=True)
            urllib.request.urlretrieve(file_url, local_tmp)
        base = target_path
        if base.endswith(".zip"):
            base = base[:-4]
        shutil.make_archive(base, "zip", tmp_dir)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _create_dataset(
    project_id: str,
    name: str,
    cluster_id: Optional[str] = None,
) -> dict:
    """Create a new Lightning Dataset via the API.

    This only creates the dataset record. It does not create a version;
    call ``_create_dataset_version`` afterwards before uploading any files.

    Args:
        project_id: The teamspace/project ID.
        name: Dataset name.
        cluster_id: Optional cloud account/cluster ID for storage.

    Returns:
        The created dataset dict (containing ``id``).
    """
    client = LightningClient(retry=False)
    api_client: ApiClient = client.api_client

    body: dict = {"name": name}
    if cluster_id:
        body["cluster_id"] = cluster_id

    resp = api_client.request(
        "POST",
        f"{env.LIGHTNING_CLOUD_URL}/v1/projects/{project_id}/lit-datasets",
        headers=api_client.default_headers,
        body=body,
        _preload_content=True,
    )
    return json.loads(resp.data) if resp.data else {}


def _create_dataset_version(
    project_id: str,
    dataset_id: str,
    cluster_id: str,
    version: Optional[str] = None,
) -> dict:
    """Create a new version of a Lightning Dataset via the API.

    A dataset version must exist before any files can be uploaded, since the
    upload endpoints are scoped to a specific version. When ``version`` is
    omitted, the backend auto-assigns the next ``vN`` tag.

    Args:
        project_id: The teamspace/project ID.
        dataset_id: The ID of the dataset to add a version to.
        cluster_id: Cloud account/cluster ID for storage (required).
        version: Optional explicit version tag (e.g. ``"v1"``).

    Returns:
        The created version dict (containing ``version``).
    """
    client = LightningClient(retry=False)
    api_client: ApiClient = client.api_client

    body: dict = {"cluster_id": cluster_id}
    if version:
        body["version"] = version

    resp = api_client.request(
        "POST",
        f"{env.LIGHTNING_CLOUD_URL}/v1/projects/{project_id}/lit-datasets/{dataset_id}/versions",
        headers=api_client.default_headers,
        body=body,
        _preload_content=True,
    )
    return json.loads(resp.data) if resp.data else {}


class _DatasetFileUploader:
    """Handles the upload of dataset files using the Lit Dataset Service API."""

    def __init__(
        self,
        client: LightningClient,
        dataset_id: str,
        version: str,
        teamspace_id: str,
        file_path: str,
        remote_path: str,
        progress_bar: bool,
        max_workers: Optional[int] = None,
        shared_progress: Optional[tqdm] = None,
    ) -> None:
        self._client = client
        self._dataset_id = dataset_id
        self._version = version
        self._teamspace_id = teamspace_id
        self._local_path = file_path
        self._remote_path = remote_path
        self._filesize = os.path.getsize(file_path)
        self._chunk_size = int(os.environ.get("LIGHTNING_MULTI_PART_PART_SIZE", _MAX_SIZE_MULTI_PART_CHUNK))
        assert self._chunk_size < _SIZE_LIMIT_SINGLE_PART
        # Within-file part concurrency; an explicit value (from the file-parallel
        # orchestrator) overrides the env default so total concurrency stays bounded.
        if max_workers is not None:
            self._max_workers = max_workers
        else:
            self._max_workers = int(os.environ.get("LIGHTNING_MULTI_PART_MAX_WORKERS", _MAX_WORKERS))
        self._batch_size = int(os.environ.get("LIGHTNING_MULTI_PART_BATCH_SIZE", _MAX_BATCH_SIZE))
        self._multipart_threshold = int(os.environ.get("LIGHTNING_MULTIPART_THRESHOLD", _MAX_SIZE_MULTI_PART_CHUNK))
        # When a shared (aggregate) progress bar is provided, update it instead of
        # creating per-file/per-chunk bars (which get messy under parallel uploads).
        self._shared_progress = shared_progress
        if shared_progress is not None:
            self._progress_bar = shared_progress
        elif progress_bar:
            self._progress_bar = tqdm(
                desc=f"Uploading {os.path.split(file_path)[1]}",
                total=self._filesize,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                leave=False,
                position=-1,
                mininterval=1,
            )
        else:
            self._progress_bar = None

    def __call__(self) -> None:
        count = 1 if self._filesize <= self._multipart_threshold else math.ceil(self._filesize / self._chunk_size)
        return self._multipart_upload(count=count)

    @property
    def _base_url(self) -> str:
        return (
            f"{env.LIGHTNING_CLOUD_URL}/v1/projects/{self._teamspace_id}"
            f"/lit-datasets/{self._dataset_id}/versions/{self._version}"
        )

    def _request(self, method, url, body=None):
        api_client: ApiClient = self._client.api_client
        resp = api_client.request(
            method,
            url,
            headers=api_client.default_headers,
            body=body,
            _preload_content=True,
        )
        return json.loads(resp.data) if resp.data else {}

    def _multipart_upload(self, count):
        resp = self._request("POST", f"{self._base_url}/uploads", body={"filepath": self._remote_path})
        upload_id = resp.get("uploadId") or resp.get("upload_id")
        if not upload_id:
            raise ValueError(f"Could not find upload_id in response: {resp}")
        with ThreadPoolExecutor(max_workers=self._max_workers) as p:
            parts = list(range(1, count + 1))
            batches = [parts[i : i + self._batch_size] for i in range(0, len(parts), self._batch_size)]
            completed = []
            for batch in tqdm(
                batches,
                desc=f"Chunks {os.path.split(self._local_path)[1]}",
                leave=False,
                disable=self._shared_progress is not None,
            ):
                completed.extend(self._process_upload_batch(executor=p, batch=batch, upload_id=upload_id))
        self._request(
            "POST",
            f"{self._base_url}/uploads/{upload_id}/complete",
            body={
                "filepath": self._remote_path,
                "parts": [{"etag": p["etag"], "partNumber": str(p["part_number"])} for p in completed],
            },
        )

    def _process_upload_batch(self, executor, batch, upload_id):
        urls = self._request_urls(parts=batch, upload_id=upload_id)
        func = partial(self._handle_uploading_single_part, upload_id=upload_id)
        return list(executor.map(func, urls))

    def _request_urls(self, parts, upload_id):
        resp = self._request(
            "POST",
            f"{self._base_url}/uploads/{upload_id}/parts",
            body={"filepath": self._remote_path, "parts": [str(p) for p in parts]},
        )
        return resp.get("urls", [])

    def _handle_uploading_single_part(self, presigned_url, upload_id):
        try:
            return self._handle_upload_presigned_url(presigned_url)
        except Exception:
            part_number = presigned_url.get("partNumber") or presigned_url.get("part_number")
            return self._error_handling_upload(part=int(part_number), upload_id=upload_id)

    def _handle_upload_presigned_url(self, presigned_url):
        part_number = presigned_url.get("partNumber") or presigned_url.get("part_number")
        url = presigned_url.get("url")
        with open(self._local_path, "rb") as f:
            f.seek((int(part_number) - 1) * self._chunk_size)
            data = f.read(self._chunk_size)
        response = requests.put(url, data=data)
        response.raise_for_status()
        if self._progress_bar is not None:
            self._progress_bar.update(len(data))
        return {"etag": response.headers.get("ETag"), "part_number": part_number}

    @backoff.on_exception(backoff.expo, (requests.exceptions.HTTPError), max_tries=10)
    def _error_handling_upload(self, part, upload_id):
        urls = self._request_urls(parts=[part], upload_id=upload_id)
        if len(urls) != 1:
            raise ValueError(f"expected 1 URL, got {len(urls)} for part {part}")
        return self._handle_upload_presigned_url(presigned_url=urls[0])


def _upload_dataset_files(
    project_id: str,
    dataset_id: str,
    version: str,
    file_paths: List[Union[str, Path]],
    remote_paths: List[str],
    progress_bar: bool = True,
    num_workers: int = _DEFAULT_UPLOAD_WORKERS,
) -> None:
    """Upload files to a version using multipart uploads, files in parallel.

    A total concurrency budget of ``num_workers`` is split across files and the
    parts within each file: ``file_workers = min(num_workers, n_files)`` files
    upload at once, each using ``max(1, num_workers // file_workers)`` part
    workers. So many-small-file datasets parallelize across files (overlapping
    the per-file create/parts/complete round-trips), while a few-large-file
    dataset still chunks within each file — without exceeding the budget.
    """
    import concurrent.futures
    from concurrent.futures import ThreadPoolExecutor

    assert len(file_paths) == len(remote_paths)
    if not file_paths:
        return

    client = LightningClient(retry=False)
    file_workers = max(1, min(num_workers, len(file_paths)))
    part_workers = max(1, num_workers // file_workers)

    total_bytes = sum(os.path.getsize(str(p)) for p in file_paths)
    pbar = (
        tqdm(total=total_bytes, desc="Uploading dataset", unit="B", unit_scale=True, unit_divisor=1000, mininterval=1)
        if progress_bar
        else None
    )

    def _upload_one(filepath: Union[str, Path], remote_path: str) -> None:
        _DatasetFileUploader(
            client=client,
            dataset_id=dataset_id,
            version=version,
            teamspace_id=project_id,
            file_path=str(filepath),
            remote_path=str(remote_path),
            progress_bar=False,
            max_workers=part_workers,
            shared_progress=pbar,
        )()

    try:
        with ThreadPoolExecutor(max_workers=file_workers) as executor:
            futures = [executor.submit(_upload_one, fp, rp) for fp, rp in zip(file_paths, remote_paths)]
            concurrent.futures.wait(futures)
            for fut in futures:
                fut.result()  # surface any upload error
    finally:
        if pbar:
            pbar.close()


def _complete_dataset_upload(project_id: str, dataset_id: str, version: str) -> None:
    """Signal that all files for a dataset version have been uploaded."""
    client = LightningClient(retry=False)
    api_client: ApiClient = client.api_client
    api_client.request(
        "POST",
        f"{env.LIGHTNING_CLOUD_URL}/v1/projects/{project_id}" f"/lit-datasets/{dataset_id}/versions/{version}/complete",
        headers=api_client.default_headers,
        body={},
        _preload_content=True,
    )


def _list_datasets(project_id: str) -> list:
    """List all Lightning Datasets in a Teamspace."""
    client = LightningClient(retry=False)
    api_client: ApiClient = client.api_client
    resp = api_client.request(
        "GET",
        f"{env.LIGHTNING_CLOUD_URL}/v1/projects/{project_id}/lit-datasets",
        headers=api_client.default_headers,
        _preload_content=True,
    )
    data = json.loads(resp.data) if resp.data else {}
    return data.get("datasets", [])


def _list_dataset_versions(project_id: str, dataset_id: str) -> list:
    """List all versions of a Lightning Dataset."""
    client = LightningClient(retry=False)
    api_client: ApiClient = client.api_client
    resp = api_client.request(
        "GET",
        f"{env.LIGHTNING_CLOUD_URL}/v1/projects/{project_id}/lit-datasets/{dataset_id}/versions",
        headers=api_client.default_headers,
        _preload_content=True,
    )
    data = json.loads(resp.data) if resp.data else {}
    return data.get("versions", [])


def _get_dataset_by_name(project_id: str, dataset_name: str) -> Optional[dict]:
    """Look up a Lightning Dataset by name."""
    datasets = _list_datasets(project_id)
    for ds in datasets:
        if ds.get("name") == dataset_name:
            return ds
    return None


def _upload_dataset(
    project_id: str,
    name: str,
    version: Optional[str],
    cluster_id: Optional[str],
    file_paths: List[Path],
    relative_paths: List[str],
    progress_bar: bool,
    num_workers: int = _DEFAULT_UPLOAD_WORKERS,
) -> dict:
    """Perform a full dataset upload.

    If a dataset with the given name already exists, a new version is created
    on the existing dataset.  Otherwise a new dataset record is created first.
    """
    existing = _get_dataset_by_name(project_id=project_id, dataset_name=name)
    if existing:
        dataset_id = existing.get("id")
        # compute the next version number from existing versions
        if version is None:
            versions = _list_dataset_versions(project_id=project_id, dataset_id=dataset_id)
            max_v = 0
            for v in versions:
                ver_str = v.get("version", "") if isinstance(v, dict) else str(v)
                if ver_str.startswith("v"):
                    try:
                        n = int(ver_str[1:])
                        max_v = max(max_v, n)
                    except ValueError:
                        pass
            version = f"v{max_v + 1}"
    else:
        ds = _create_dataset(
            project_id=project_id,
            name=name,
            cluster_id=cluster_id,
        )
        dataset_id = ds.get("id")

    # CreateLitDataset only creates the dataset record; a version must be
    # created explicitly before the version-scoped upload endpoints exist.
    ver = _create_dataset_version(
        project_id=project_id,
        dataset_id=dataset_id,
        cluster_id=cluster_id,
        version=version,
    )
    ds_version = ver.get("version")

    _upload_dataset_files(
        project_id=project_id,
        dataset_id=dataset_id,
        version=ds_version,
        file_paths=file_paths,
        remote_paths=relative_paths,
        progress_bar=progress_bar,
        num_workers=num_workers,
    )
    _complete_dataset_upload(
        project_id=project_id,
        dataset_id=dataset_id,
        version=ds_version,
    )
    return {"id": dataset_id, "name": name, "version": ds_version}
