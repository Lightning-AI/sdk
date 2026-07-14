from typing import Optional
import json
import os
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.lightning_cloud.openapi.api_client import ApiClient
from lightning_sdk.lightning_cloud import env


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
