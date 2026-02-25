import os
from typing import Dict, List

import requests
from tqdm.auto import tqdm

from lightning_sdk.api.utils import (
    _authenticate_and_get_token,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class FilesystemApi:
    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)
        self._token = _authenticate_and_get_token(self._client)

    def list_files(self, teamspace_id: str, path: str, recursive: bool = False) -> List[Dict]:
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
        token = _authenticate_and_get_token(self._client)

        query_params = {
            "token": token,
        }

        r = requests.get(
            f"{self._client.api_client.configuration.host}/v1/projects/{teamspace_id}/artifacts/blobs/{path}",
            params=query_params,
            stream=True,
            allow_redirects=True,
        )

        if r.status_code != 200:
            raise RuntimeError(f"Failed to download file: {r.status_code}")

        total_length = int(r.headers.get("content-length", 0))

        if progress_bar and total_length > 0:
            pbar = tqdm(
                desc=f"Downloading {os.path.split(path)[1]}",
                total=total_length,
                unit="B",
                unit_scale=True,
                unit_divisor=1000,
            )

            pbar_update = pbar.update
        else:
            pbar_update = lambda x: None

        target_dir = os.path.split(target_path)[0]
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        with open(target_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=4096 * 8):
                f.write(chunk)
                pbar_update(len(chunk))
