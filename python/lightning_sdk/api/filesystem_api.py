import concurrent
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional

import requests
from tqdm.auto import tqdm

from lightning_sdk.api.utils import (
    _authenticate_and_get_token,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class FilesystemApi:
    """Internal API client for direct artifact filesystem operations (list, download)."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)
        self._token = _authenticate_and_get_token(self._client)

    @property
    def client(self) -> LightningClient:
        """The underlying ``LightningClient`` instance.

        Returns:
            LightningClient: The underlying ``LightningClient`` instance.
        """
        return self._client

    def list_files(self, teamspace_id: str, path: str, recursive: bool = False) -> List[Dict]:
        """List artifact entries under ``path`` in the teamspace, optionally recursing into subdirectories.

        Args:
            teamspace_id: The teamspace that owns the artifacts.
            path: The artifact folder path to list.
            recursive: When ``True``, list files in all subdirectories recursively.

        Returns:
            List[Dict]: A list of artifact entry dicts from the API tree response.

        Raises:
            RuntimeError: If the server returns a non-200 status code.
        """
        path = path.strip("/")
        query_params = {"recursive": "false"}
        if recursive:
            query_params["recursive"] = "true"

        query_params["token"] = self._token
        r = requests.get(
            f"{self._client.api_client.configuration.host}/v1/projects/{teamspace_id}/artifacts/trees/{path}",
            params=query_params,
        )
        if r.status_code != 200:
            raise RuntimeError(f"Failed to list files: {r.status_code}")
        return r.json().get("tree", [])

    def download_file(self, path: str, target_path: str, teamspace_id: str, progress_bar: bool = True) -> None:
        """Download a single artifact file from the teamspace to a local path.

        Args:
            path: The artifact path within the teamspace to download.
            target_path: Local filesystem path to write the downloaded file to.
            teamspace_id: The teamspace that owns the artifact.
            progress_bar: Whether to display a tqdm progress bar during download.
        """
        self._download_single_file(path, Path(target_path), teamspace_id, self._token, progress_bar=progress_bar)

    def _download_single_file(
        self,
        remote_path: str,
        local_path: Path,
        teamspace_id: str,
        token: str,
        pbar: Optional[tqdm] = None,
        progress_bar: bool = False,
    ) -> None:
        """Download a single artifact file.

        Streams the single, downloaded artifact file to ``local_path`` and
        optionally updates a shared progress bar.

        Args:
            remote_path: The artifact path within the teamspace to download.
            local_path: Local filesystem path to write the downloaded file to.
            teamspace_id: The teamspace that owns the artifact.
            token: Authentication token for the download request.
            pbar: Optional shared tqdm progress bar to update with downloaded bytes.
            progress_bar: When ``True`` and ``pbar`` is ``None``, create a per-file progress bar.

        Raises:
            RuntimeError: If the server returns a non-200 status code.
        """
        r = requests.get(
            f"{self._client.api_client.configuration.host}/v1/projects/{teamspace_id}/artifacts/blobs/{remote_path}",
            params={"token": token},
            stream=True,
            allow_redirects=True,
        )
        if r.status_code != 200:
            raise RuntimeError(f"Failed to download {remote_path!r}: {r.status_code}")

        owned_pbar = None
        if pbar is None and progress_bar:
            total_length = int(r.headers.get("content-length", 0))
            owned_pbar = tqdm(
                desc=f"Downloading {os.path.split(remote_path)[1]}",
                total=total_length if total_length > 0 else None,
                unit="B",
                unit_scale=True,
                unit_divisor=1000,
            )
            pbar = owned_pbar

        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=4096 * 8):
                f.write(chunk)
                if pbar is not None:
                    pbar.update(len(chunk))

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
        """
        path = path.strip("/")
        entries = self.list_files(teamspace_id, path, recursive=True)
        total_size = sum(f.get("size", 0) for f in entries)
        files = [e for e in entries if e.get("type") == "blob"]

        if num_workers is None:
            num_workers = os.cpu_count() * 4

        download_dir = Path(target_path)
        download_dir.mkdir(parents=True, exist_ok=True)

        pbar = None
        if progress_bar:
            pbar = tqdm(
                desc="Downloading files",
                total=total_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1000,
                mininterval=1,
            )

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(
                    self._download_single_file,
                    f"{path}/{entry['path']}",
                    download_dir / entry["path"],
                    teamspace_id,
                    self._token,
                    pbar,
                )
                for entry in files
            ]
            concurrent.futures.wait(futures)

        if pbar:
            pbar.set_description("Download complete")
            pbar.refresh()
            pbar.close()
