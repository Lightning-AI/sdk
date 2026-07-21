from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

from lightning_sdk.api.utils import AccessibleResource, raise_access_error_if_not_allowed
from lightning_sdk.lightning_cloud.utils.dataset import (
    _DEFAULT_DOWNLOAD_PART_SIZE,
    _DEFAULT_DOWNLOAD_WORKERS,
    _DEFAULT_UPLOAD_WORKERS,
    _download_dataset_version,
    _get_dataset_by_name,
    _list_dataset_versions,
    _list_datasets,
    _parse_dataset_path,
    _resolve_dataset_id_and_version,
    _upload_dataset,
)
from lightning_sdk.models import _get_teamspace
from lightning_sdk.teamspace import _list_files


@dataclass
class UploadedDatasetInfo:
    """Metadata returned after a successful dataset upload.

    Attributes:
        name: The dataset name.
        version: The assigned version tag (e.g. ``"v1"``).
        teamspace: Name of the teamspace the dataset was uploaded to.
    """

    name: str
    version: str
    teamspace: str


@dataclass
class DownloadedDatasetInfo:
    """Metadata returned after a successful dataset download.

    Attributes:
        path: The local directory containing the dataset, or the ZIP archive
            path when downloaded with ``as_zip=True``.
        name: The dataset name.
        version: The version tag that was downloaded (e.g. ``"v1"``).
    """

    path: str
    name: str
    version: str


def upload_dataset(
    name: str,
    path: Union[str, Path, List[Union[str, Path]]] = ".",
    cloud_account: Optional[str] = None,
    progress_bar: bool = True,
    num_workers: int = _DEFAULT_UPLOAD_WORKERS,
) -> UploadedDatasetInfo:
    """Upload a dataset to Lightning Datasets.

    Files upload concurrently (many-small-file datasets parallelize across files;
    large files chunk within-file), bounded by ``num_workers`` total.

    Args:
        name: Lightning path to dataset in the format
            ``<ORGANIZATION>/<TEAMSPACE>/<DATASET-NAME>`` or
            ``<ORGANIZATION>/<TEAMSPACE>/<DATASET-NAME>/<VERSION>``.
        path: Local file or directory to upload (defaults to current directory).
        cloud_account: Cloud account to store the dataset files in.
            Falls back to teamspace default when not provided.
        progress_bar: Whether to display an upload progress bar.
        num_workers: total upload concurrency, split across files and their parts
            (default 16).

    Returns:
        UploadedDatasetInfo: Metadata about the newly uploaded dataset version.
    """
    org_name, ts_name, dataset_name, version = _parse_dataset_path(name)
    teamspace = _get_teamspace(name=ts_name, organization=org_name)
    raise_access_error_if_not_allowed(AccessibleResource.Models, teamspace.id)
    project_id = teamspace.id

    if not path:
        raise ValueError("No path provided to upload")

    if isinstance(path, (str, Path)):
        path = [path]

    file_paths, relative_paths = [], []
    for p in path:
        lpaths, rpaths = _list_files(p)
        file_paths.extend(lpaths)
        relative_paths.extend(rpaths)

    if not file_paths:
        raise FileNotFoundError(f"The path to upload doesn't contain any files: {path}")
    if len(relative_paths) != len(set(relative_paths)):
        raise RuntimeError(f"Duplicate relative paths detected. Files: {file_paths}")

    if cloud_account is None:
        cloud_account = teamspace._teamspace_api._determine_cloud_account(project_id)

    result = _upload_dataset(
        project_id=project_id,
        name=dataset_name,
        version=version,
        cluster_id=cloud_account,
        file_paths=file_paths,
        relative_paths=relative_paths,
        progress_bar=progress_bar,
        num_workers=num_workers,
    )
    return UploadedDatasetInfo(
        name=dataset_name,
        version=result["version"],
        teamspace=teamspace.name,
    )


def download_dataset(
    name: str,
    target_path: str = ".",
    cluster_id: Optional[str] = None,
    num_workers: int = _DEFAULT_DOWNLOAD_WORKERS,
    part_size: int = _DEFAULT_DOWNLOAD_PART_SIZE,
    as_zip: bool = False,
    unzip: bool = False,
) -> DownloadedDatasetInfo:
    """Download a dataset version from Lightning Datasets.

    By default, files are downloaded into a directory. Set ``as_zip=True`` to
    package that file tree into a ZIP archive, or ``unzip=True`` to safely
    extract a dataset version stored as exactly one ZIP artifact. Files download
    concurrently, each fetched via chunked HTTP-Range requests.

    Args:
        name: Lightning path to dataset in the format
            ``<ORGANIZATION>/<TEAMSPACE>/<DATASET-NAME>`` or
            ``<ORGANIZATION>/<TEAMSPACE>/<DATASET-NAME>/<VERSION>``.
            If no version specified, defaults to the most recent version.
        target_path: Local directory to download the dataset into.
            Defaults to the current directory (``"."``).
        cluster_id: Optional cluster ID to download from.
        num_workers: number of concurrent download threads (default 16).
        part_size: byte-range part size for splitting large files (default 64 MB).
        as_zip: Package the downloaded file tree into a ZIP archive.
        unzip: Extract a version stored as exactly one ZIP artifact into a
            directory. This is never enabled automatically.

    Returns:
        DownloadedDatasetInfo: Metadata about the downloaded dataset, including
            the local path, dataset name, and version.

    Raises:
        ValueError: If ``as_zip`` and ``unzip`` are both enabled, or if
            ``unzip=True`` is used with a version that is not exactly one ZIP
            artifact.
    """
    if as_zip and unzip:
        raise ValueError("`as_zip` and `unzip` cannot both be True.")

    org_name, ts_name, dataset_name, version = _parse_dataset_path(name)
    teamspace = _get_teamspace(name=ts_name, organization=org_name)
    raise_access_error_if_not_allowed(AccessibleResource.Models, teamspace.id)
    project_id = teamspace.id

    # One API round-trip resolves both the dataset id and (if unspecified) the
    # current version, avoiding a second datasets-list call before download.
    dataset_id, version = _resolve_dataset_id_and_version(project_id, dataset_name, version)

    import os

    base_name = f"{dataset_name}_{version}"
    output_path = os.path.join(target_path, f"{base_name}.zip" if as_zip else base_name)
    _download_dataset_version(
        project_id=project_id,
        dataset_name=dataset_name,
        version=version,
        target_path=output_path,
        cluster_id=cluster_id,
        dataset_id=dataset_id,
        num_workers=num_workers,
        part_size=part_size,
        as_zip=as_zip,
        unzip=unzip,
    )
    return DownloadedDatasetInfo(path=output_path, name=dataset_name, version=version)


def list_datasets(name: str) -> list:
    """List all datasets in a teamspace.

    Args:
        name: Teamspace path in the format ``<ORGANIZATION>/<TEAMSPACE>``.

    Returns:
        List of dataset objects.
    """
    parts = name.split("/")
    if len(parts) != 2:
        raise ValueError(f"Expected teamspace path in format '<ORG>/<TEAMSPACE>', got '{name}'")
    org_name, ts_name = parts
    teamspace = _get_teamspace(name=ts_name, organization=org_name)
    raise_access_error_if_not_allowed(AccessibleResource.Models, teamspace.id)
    return _list_datasets(project_id=teamspace.id)


def list_dataset_versions(name: str) -> list:
    """List all versions of a dataset.

    Args:
        name: Fully-qualified dataset name in the format
            ``<ORGANIZATION>/<TEAMSPACE>/<DATASET-NAME>``.

    Returns:
        List of version objects.
    """
    org_name, ts_name, dataset_name, _ = _parse_dataset_path(name)
    teamspace = _get_teamspace(name=ts_name, organization=org_name)
    raise_access_error_if_not_allowed(AccessibleResource.Models, teamspace.id)
    project_id = teamspace.id

    ds = _get_dataset_by_name(project_id=project_id, dataset_name=dataset_name)
    if ds is None:
        raise ValueError(f"Dataset '{dataset_name}' not found.")
    return _list_dataset_versions(project_id=project_id, dataset_id=ds.get("id"))
