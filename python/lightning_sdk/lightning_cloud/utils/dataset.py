from typing import Optional, Tuple
import json
import os
import logging
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.lightning_cloud.openapi.api_client import ApiClient
from lightning_sdk.lightning_cloud import env

logger = logging.getLogger(__name__)

# Multipart upload chunk size: 5 MiB
_MULTIPART_CHUNK_SIZE = 5 * 1024 * 1024


def _resolve_dataset_name_to_id(project_id: str, dataset_id: str) -> Tuple[str, Optional[str]]:
    """Resolve a dataset name to its ULID and current version.

    Returns a tuple of (resolved_ulid, current_version).
    If no current version exists, current_version is None.
    Raises ValueError if the dataset cannot be found.
    """
    client = LightningClient(retry=False)

    # Try the lit-datasets endpoint first (new API)
    try:
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
            if ds.get("name") == dataset_id:
                ds_id = ds.get("id")
                if not ds_id:
                    raise ValueError(f"Dataset '{dataset_id}' found but has no ID.")
                # Determine current version
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
                return ds_id, current_version
    except ValueError:
        raise
    except Exception as e:
        logger.debug("lit-datasets API lookup failed: %s", e)

    # Fallback: list datasets via the old API
    try:
        response = client.dataset_service_list_datasets(project_id=project_id)
        for dataset in (response.datasets or []):
            if getattr(dataset, "name", None) == dataset_id:
                ds_id = getattr(dataset, "id", None)
                if not ds_id:
                    raise ValueError(f"Dataset '{dataset_id}' found but has no ID.")
                current_version = None
                default = getattr(dataset, "default_version", None)
                if default and getattr(default, "version", None):
                    current_version = getattr(default, "version")
                if not current_version:
                    latest = getattr(dataset, "latest_version", None)
                    if latest and getattr(latest, "version", None):
                        current_version = getattr(latest, "version")
                if not current_version:
                    current_version = getattr(dataset, "version", None)
                return ds_id, current_version
    except Exception as e:
        logger.debug("dataset_service_list_datasets failed: %s", e)

    raise ValueError(f"Dataset '{dataset_id}' not found in project '{project_id}'.")


def _get_default_cluster_id(project_id: str, dataset_ulid: Optional[str] = None) -> str:
    """Get the default cluster ID for a project.

    First checks project cluster bindings. If none are found and a
    dataset_ulid is provided, falls back to querying an existing
    dataset version to reuse its cluster.
    """
    client = LightningClient(retry=False)

    # 1. Check project cluster bindings via cluster_service_list_project_clusters
    try:
        resp = client.cluster_service_list_project_clusters(project_id=project_id)
        clusters = getattr(resp, "clusters", None)
        if clusters:
            for cluster in clusters:
                cid = getattr(cluster, "id", None)
                if cid:
                    return cid
    except Exception as e:
        logger.debug("list project clusters failed: %s", e)

    # 2. Fallback: try to get the cluster from an existing dataset version
    if dataset_ulid:
        cloud_url = env.LIGHTNING_CLOUD_URL
        api_client = client.api_client

        # Try the lit-datasets GET endpoint (new API)
        try:
            resp = api_client.request(
                "GET",
                f"{cloud_url}/v1/projects/{project_id}/lit-datasets/{dataset_ulid}",
                headers=api_client.default_headers,
                _preload_content=True,
            )
            data = json.loads(resp.data) if resp.data else {}
            ds = data.get("data", data)

            # Check default/latest version for cluster info
            for ver_key in ("default_version", "defaultVersion", "latest_version", "latestVersion"):
                ver = ds.get(ver_key)
                if ver:
                    cid = ver.get("cluster_id") or ver.get("clusterId")
                    if cid:
                        return cid

            # Check versions list
            versions = ds.get("versions", [])
            for ver in versions:
                cid = ver.get("cluster_id") or ver.get("clusterId")
                if cid:
                    return cid
        except Exception as e:
            logger.debug("lit-datasets GET for cluster info failed: %s", e)

        # Try the old dataset_service_get_dataset API as fallback
        try:
            ds = client.dataset_service_get_dataset(
                project_id=project_id, id=dataset_ulid
            )
            cid = getattr(ds, "cluster_id", None) or getattr(ds, "clusterId", None)
            if cid:
                return cid
        except Exception as e:
            logger.debug("dataset_service_get_dataset for cluster info failed: %s", e)

    raise ValueError(f"No default cluster found for project '{project_id}'. Please specify --cluster-id.")


def _resolve_dataset_version(project_id: str, dataset_id: str, version: Optional[str] = None, for_upload: bool = False) -> str:
    """Resolve the dataset version, defaulting to the most recent if not provided.

    For downloads, returns the current version. For uploads, auto-increments
    to the next version number.

    Args:
        project_id: The project ID.
        dataset_id: The dataset ID (name).
        version: Optional version. If None, the most recent/next version is returned.
        for_upload: If True, auto-increment the version for uploads.

    Returns:
        The resolved version string.

    Raises:
        ValueError: If the dataset cannot be found or has no version.
    """
    import re

    if version:
        return version

    # Use the centralised resolver to find current version
    try:
        _, current_version = _resolve_dataset_name_to_id(project_id, dataset_id)
    except ValueError:
        if for_upload:
            return "v1"
        raise

    if for_upload:
        # Auto-increment the version number for uploads
        if current_version:
            match = re.match(r"^v(\d+)$", current_version)
            if match:
                next_num = int(match.group(1)) + 1
                return f"v{next_num}"
        return "v1"

    # For download: return the current version or raise
    if current_version:
        return current_version

    raise ValueError(f"Dataset '{dataset_id}' not found in project '{project_id}', or it has no versions.")

def _download_dataset_version(
    project_id: str,
    dataset_id: str,
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
        dataset_id: The dataset ID (name or ULID).
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

    # Resolve dataset name to ULID if needed
    resolved_id = dataset_id

    # Try to list datasets to resolve name -> ULID
    try:
        resp = api_client.request(
            "GET",
            f"{cloud_url}/v1/projects/{project_id}/lit-datasets",
            headers=api_client.default_headers,
            _preload_content=True,
        )
        data = json.loads(resp.data) if resp.data else {}
        for ds in data.get("datasets", []):
            if ds.get("name") == dataset_id:
                resolved_id = ds.get("id", dataset_id)
                break
    except Exception:
        pass

    # Get presigned file URLs from the files endpoint
    files_url = f"{cloud_url}/v1/projects/{project_id}/datasets/{resolved_id}/versions/{version}/files"
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
        raise ValueError(f"No files found for dataset '{dataset_id}' version '{version}' in project '{project_id}'.")

    # Always create a proper zip archive from the downloaded files
    tmp_dir = tempfile.mkdtemp()
    try:
        for i, file_info in enumerate(files_list):
            file_url = file_info.get("url")
            if not file_url:
                continue
            # Use relative path within the zip; strip leading / to avoid absolute paths
            filepath = file_info.get("filepath", f"file_{i}")
            filepath = filepath.lstrip("/")
            # Handle subdirectories in the filepath
            local_tmp = os.path.join(tmp_dir, filepath)
            os.makedirs(os.path.dirname(local_tmp), exist_ok=True)
            urllib.request.urlretrieve(file_url, local_tmp)
        # Zip the directory - make_archive adds .zip extension, so remove it from target
        base = target_path
        if base.endswith(".zip"):
            base = base[:-4]
        shutil.make_archive(base, "zip", tmp_dir)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

def upload_dataset(
    project_id: str,
    dataset_id: str,
    version: str,
    file_path: str,
    cluster_id: Optional[str] = None,
):
    """Upload a file as a dataset version.

    Uses the lit-datasets multipart upload API:
    1. Resolve dataset name to ULID.
    2. Create a new dataset version via POST.
    3. Upload the file in chunks via presigned S3 URLs.
    4. Mark the upload as complete.

    Args:
        project_id: The project ID.
        dataset_id: The dataset ID (name).
        version: The dataset version (e.g. "v2").
        file_path: Path to the file to upload.
        cluster_id: Optional cluster ID.
    """
    import requests

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Source file not found: {file_path}")

    cloud_url = env.LIGHTNING_CLOUD_URL

    # Step 0: Resolve dataset name to ULID
    try:
        dataset_ulid, _ = _resolve_dataset_name_to_id(project_id, dataset_id)
    except ValueError as e:
        raise ValueError(f"Cannot find dataset '{dataset_id}': {e}") from e

    # Step 1: Resolve cluster ID if not provided
    if not cluster_id:
        try:
            cluster_id = _get_default_cluster_id(project_id, dataset_ulid=dataset_ulid)
        except ValueError as e:
            raise ValueError(f"Cannot determine cluster for upload: {e}") from e

    client = LightningClient(retry=False)
    headers = dict(client.api_client.default_headers)

    # Step 2: Create the dataset version
    create_version_url = (
        f"{cloud_url}/v1/projects/{project_id}"
        f"/lit-datasets/{dataset_ulid}/versions"
    )
    version_body = {"clusterId": cluster_id, "version": version}
    logger.info("Creating dataset version '%s' for dataset '%s'...", version, dataset_id)
    try:
        resp = requests.post(
            create_version_url,
            json=version_body,
            headers=headers,
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Failed to create dataset version '{version}': "
                f"HTTP {resp.status_code} {resp.reason} — {resp.text[:500]}"
            )
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to create dataset version '{version}': {e}") from e

    # Step 3: Create multipart upload for the file
    filename = os.path.basename(file_path)
    upload_url = (
        f"{cloud_url}/v1/projects/{project_id}"
        f"/lit-datasets/{dataset_ulid}/versions/{version}/uploads"
    )
    logger.info("Starting multipart upload for '%s'...", filename)
    try:
        resp = requests.post(
            upload_url,
            json={"filepath": filename},
            headers=headers,
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Failed to start multipart upload: "
                f"HTTP {resp.status_code} {resp.reason} — {resp.text[:500]}"
            )
        upload_data = resp.json()
        upload_id = upload_data.get("uploadId")
        if not upload_id:
            raise RuntimeError(f"No uploadId in response: {resp.text[:500]}")
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to start multipart upload: {e}") from e

    # Step 4: Split file into chunks, get presigned URLs, upload each chunk
    file_size = os.path.getsize(file_path)
    total_parts = (file_size + _MULTIPART_CHUNK_SIZE - 1) // _MULTIPART_CHUNK_SIZE

    parts_url = (
        f"{cloud_url}/v1/projects/{project_id}"
        f"/lit-datasets/{dataset_ulid}/versions/{version}"
        f"/uploads/{upload_id}/parts"
    )

    # Generate part numbers
    part_ids = [str(i + 1) for i in range(total_parts)]
    logger.info("Getting presigned URLs for %d parts...", total_parts)

    try:
        resp = requests.post(
            parts_url,
            json={"filepath": filename, "parts": part_ids},
            headers=headers,
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Failed to get presigned URLs: "
                f"HTTP {resp.status_code} {resp.reason} — {resp.text[:500]}"
            )
        parts_data = resp.json()
        urls_info = parts_data.get("urls", [])
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to get presigned upload URLs: {e}") from e

    if len(urls_info) != total_parts:
        raise RuntimeError(
            f"Expected {total_parts} presigned URLs but got {len(urls_info)}"
        )

    completed_parts = []
    with open(file_path, "rb") as f:
        for i, part_info in enumerate(urls_info):
            part_number = i + 1
            part_signed_url = part_info.get("url")
            if not part_signed_url:
                raise RuntimeError(f"No URL for part {part_number}")

            chunk = f.read(_MULTIPART_CHUNK_SIZE)

            logger.info(
                "Uploading part %d/%d (%d bytes)...",
                part_number, total_parts, len(chunk),
            )
            try:
                part_resp = requests.put(
                    part_signed_url,
                    data=chunk,
                    timeout=300,
                )
                if part_resp.status_code not in (200, 204):
                    raise RuntimeError(
                        f"Failed to upload part {part_number}: "
                        f"HTTP {part_resp.status_code}"
                    )

                # Get ETag from response headers
                etag = part_resp.headers.get("ETag", "")
                completed_parts.append({
                    "partNumber": part_number,
                    "eTag": etag.strip('"'),
                })
            except requests.RequestException as e:
                raise RuntimeError(
                    f"Failed to upload part {part_number}: {e}"
                ) from e

    # Step 5: Complete the multipart upload
    complete_mpu_url = f"{upload_url}/{upload_id}/complete"
    logger.info("Completing multipart upload...")
    try:
        resp = requests.post(
            complete_mpu_url,
            json={"filepath": filename, "parts": completed_parts},
            headers=headers,
            timeout=30,
        )
        if resp.status_code not in (200, 201, 204):
            raise RuntimeError(
                f"Failed to complete multipart upload: "
                f"HTTP {resp.status_code} {resp.reason} — {resp.text[:500]}"
            )
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to complete multipart upload: {e}") from e

    # Step 6: Mark the dataset version upload as complete
    complete_url = f"{upload_url}/complete"
    logger.info("Finalising dataset version upload...")
    try:
        resp = requests.post(
            complete_url,
            json={},
            headers=headers,
            timeout=30,
        )
        if resp.status_code not in (200, 201, 204):
            logger.warning(
                "Upload completed but finalisation returned HTTP %s "
                "for dataset '%s' version '%s': %s",
                resp.status_code, dataset_id, version, resp.text[:500],
            )
    except requests.RequestException as e:
        logger.warning(
            "Upload completed but finalisation failed for "
            "dataset '%s' version '%s': %s",
            dataset_id, version, e,
        )

    logger.info(
        "Successfully uploaded '%s' as version '%s' of dataset '%s'.",
        filename, version, dataset_id,
    )
