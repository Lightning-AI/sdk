import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional

import backoff
import requests
from tqdm.auto import tqdm

from lightning_sdk.api.utils import (
    _DOWNLOAD_CONNECT_TIMEOUT_SECONDS,
    _DOWNLOAD_MAX_TRIES,
    _DOWNLOAD_READ_TIMEOUT_SECONDS,
    _RETRYABLE_DOWNLOAD_STATUSES,
    _authenticate_and_get_auth_headers,
    _BlobUploader,
    _collect_download_results,
    _paged_tree_entries,
    _raise_for_download_status,
    _RemoteApiError,
    _RetryableProgress,
    _stream_download_to_file,
    _TransientDownloadError,
    cached_lightning_client,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class FilesystemApi:
    """Internal API client for direct artifact filesystem operations (list, download)."""

    def __init__(self) -> None:
        self._client = cached_lightning_client()
        self._auth_headers = _authenticate_and_get_auth_headers()

    @property
    def client(self) -> LightningClient:
        """The underlying ``LightningClient`` instance.

        Returns:
            LightningClient: The underlying ``LightningClient`` instance.
        """
        return self._client

    def list_files(
        self,
        teamspace_id: str,
        path: str,
        recursive: bool = False,
        page_size: Optional[int] = None,
    ) -> List[Dict]:
        """List artifact entries under ``path`` in the teamspace, optionally recursing into subdirectories.

        Follows the listing's cursor until the last page, so large directories
        come back complete rather than truncated.

        Args:
            teamspace_id: The teamspace that owns the artifacts.
            path: The artifact folder path to list.
            recursive: When ``True``, list files in all subdirectories recursively.
            page_size: Entries to request per page; defaults to the server's page size.

        Returns:
            List[Dict]: A list of artifact entry dicts from the API tree response.

        Raises:
            RuntimeError: If the server returns a non-200 status code.
        """
        path = path.strip("/")

        def fetch_page(query_params: Dict[str, str]) -> Dict:
            query_params["recursive"] = "true" if recursive else "false"
            if page_size is not None:
                query_params["atMost"] = str(page_size)
            r = requests.get(
                f"{self._client.api_client.configuration.host}/v1/projects/{teamspace_id}/artifacts/trees/{path}",
                params=query_params,
                headers=self._auth_headers,
            )
            if r.status_code != 200:
                raise _RemoteApiError(f"Failed to list files: {r.status_code}", status_code=r.status_code)
            return r.json()

        return _paged_tree_entries(fetch_page)

    def upload_file(
        self,
        teamspace_id: str,
        file_path: str,
        remote_path: str,
        progress_bar: bool = True,
        cloud_account: Optional[str] = None,
    ) -> None:
        """Upload a local file to a path in the teamspace drive.

        The path is passed through to the server as-is, so any destination the
        drive accepts works here; a path inside a Lightning-managed folder
        namespace (e.g. ``lightning_storage/<name>/...``) creates the folder on
        first use.

        Args:
            teamspace_id: The teamspace that owns the artifacts.
            file_path: Local filesystem path of the file to upload.
            remote_path: Destination path inside the teamspace drive.
            progress_bar: Whether to display a tqdm progress bar during upload.
            cloud_account: Cloud account to store the file on. Some destinations
                require one (e.g. ``uploads/``); others pick their own storage
                and reject a mismatch.
        """
        _BlobUploader(
            client=self._client,
            endpoint_base=f"{self._client.api_client.configuration.host}/v1/projects/{teamspace_id}/artifacts",
            file_path=file_path,
            remote_path=remote_path.strip("/"),
            progress_bar=progress_bar,
            cluster_id=cloud_account,
        )()

    def download_file(self, path: str, target_path: str, teamspace_id: str, progress_bar: bool = True) -> None:
        """Download a single artifact file from the teamspace to a local path.

        Args:
            path: The artifact path within the teamspace to download.
            target_path: Local filesystem path to write the downloaded file to.
            teamspace_id: The teamspace that owns the artifact.
            progress_bar: Whether to display a tqdm progress bar during download.
        """
        self._download_single_file(path, Path(target_path), teamspace_id, progress_bar=progress_bar)

    def _download_single_file(
        self,
        remote_path: str,
        local_path: Path,
        teamspace_id: str,
        pbar: Optional[tqdm] = None,
        progress_bar: bool = False,
        expected_size: Optional[int] = None,
    ) -> None:
        """Download a single artifact file.

        Streams the single, downloaded artifact file to ``local_path`` and
        optionally updates a shared progress bar.

        Args:
            remote_path: The artifact path within the teamspace to download.
            local_path: Local filesystem path to write the downloaded file to.
            teamspace_id: The teamspace that owns the artifact.
            pbar: Optional shared tqdm progress bar to update with downloaded bytes.
            progress_bar: When ``True`` and ``pbar`` is ``None``, create a per-file progress bar.
            expected_size: Size the listing reported for this file, checked against the bytes
                that actually arrive.

        Raises:
            RuntimeError: If the server returns a non-2xx status code, or if the body that
                arrives is not the expected length. Transient failures — dropped connections,
                timeouts, and temporary server conditions — are retried with backoff first.
        """
        url = f"{self._client.api_client.configuration.host}/v1/projects/{teamspace_id}/artifacts/blobs/{remote_path}"
        owned_pbar = None

        @backoff.on_exception(backoff.expo, _TransientDownloadError, max_tries=_DOWNLOAD_MAX_TRIES)
        def download() -> None:
            nonlocal owned_pbar, pbar
            try:
                r = requests.get(
                    url,
                    headers=self._auth_headers,
                    stream=True,
                    allow_redirects=True,
                    timeout=(_DOWNLOAD_CONNECT_TIMEOUT_SECONDS, _DOWNLOAD_READ_TIMEOUT_SECONDS),
                )
            except requests.RequestException as e:
                raise _TransientDownloadError(f"Failed to download {remote_path!r}: {e}") from e

            if r.status_code in _RETRYABLE_DOWNLOAD_STATUSES:
                try:
                    _raise_for_download_status(r, remote_path)
                except RuntimeError as e:
                    raise _TransientDownloadError(str(e)) from e
            _raise_for_download_status(r, remote_path)

            if pbar is None and progress_bar:
                total_length = int(r.headers.get("content-length", 0))
                owned_pbar = tqdm(
                    desc=f"Downloading {os.path.split(remote_path)[1]}",
                    total=total_length if total_length > 0 else None,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                )
                pbar = owned_pbar

            progress = _RetryableProgress(pbar) if pbar is not None else None
            try:
                _stream_download_to_file(r, local_path, remote_path, pbar=progress, expected_size=expected_size)
            except requests.RequestException as e:
                if progress is not None:
                    progress.rollback()
                raise _TransientDownloadError(f"Failed to download {remote_path!r}: {e}") from e
            except RuntimeError as e:
                # A body shorter than the listing or Content-Length promised is a cut
                # connection, not a bad request.
                if progress is not None:
                    progress.rollback()
                raise _TransientDownloadError(str(e)) from e

        try:
            download()
        finally:
            if owned_pbar is not None:
                owned_pbar.close()

    def download_folder(
        self,
        path: str,
        target_path: str,
        teamspace_id: str,
        progress_bar: bool = True,
        num_workers: Optional[int] = None,
    ) -> None:
        """Download all files under ``path`` in the teamspace to a local directory using a thread pool.

        Args:
            path: The artifact folder path within the teamspace to download.
            target_path: Local directory to write the downloaded files to.
            teamspace_id: The teamspace that owns the artifacts.
            progress_bar: Whether to display a tqdm progress bar during download.
            num_workers: Number of parallel download threads; defaults to ``cpu_count * 4``.

        Raises:
            RuntimeError: If any file failed to download. A partial folder is never reported
                as a success.
        """
        path = path.strip("/")
        entries = self.list_files(teamspace_id, path, recursive=True)
        total_size = sum(f.get("size", 0) for f in entries)
        files = [e for e in entries if e.get("type") == "blob"]

        if num_workers is None:
            num_workers = (os.cpu_count() or 1) * 4

        download_dir = Path(target_path)
        download_dir.mkdir(parents=True, exist_ok=True)

        pbar = None
        if progress_bar:
            pbar = tqdm(
                desc="Downloading files",
                total=total_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                mininterval=1,
            )

        try:
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [
                    executor.submit(
                        self._download_single_file,
                        f"{path}/{entry['path']}",
                        download_dir / entry["path"],
                        teamspace_id,
                        pbar,
                        expected_size=entry.get("size"),
                    )
                    for entry in files
                ]
                _collect_download_results(futures, path)

            if pbar:
                pbar.set_description("Download complete")
                pbar.refresh()
        finally:
            if pbar:
                pbar.close()
