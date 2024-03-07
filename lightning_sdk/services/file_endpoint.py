import os
from time import sleep
from typing import Any, Dict, Optional

import requests

_FILE_TO_UPLOADS_KEY = "files_to_upload"
_DOWNLOAD_IDS_KEY = "download_ids"


class FileEndpoint:
    """This class is used to communicate with the File Endpoint."""

    def __init__(
        self,
        url: str,
    ) -> None:
        """Constructor of the FileEndpoint.

        Args:
            url: The url of the Studio File Endpoint Service

        """
        self.url = url

    def run(
        self, args: Optional[Dict[str, str]] = None, files: Optional[Dict[str, str]] = None, output_dir: str = "results"
    ) -> None:
        """The run method executes the file endpoint.

        Args:
            args: The arguments sent as json data to the file endpoint
            files: The files to be uploaded to the file endpoint
            output_dir: The directory output where the artifacts files will be downloaded.

        """
        if files is None:
            files = {}
        if args is None:
            args = {}

        response = requests.post(self.url, json=args)

        if response.status_code != 200:
            raise Exception(f"The endpoint isn't reachable. Status code: {response.status_code}")

        data = response.json()

        if _FILE_TO_UPLOADS_KEY in data:
            self._upload_files(data, files)

        data = self._check_progress(data)

        if _DOWNLOAD_IDS_KEY in data:
            self._download_files(data, output_dir)

    def _upload_files(self, data: Dict[str, Any], files: Dict[str, str]) -> None:
        """Upload the files to the Studio."""
        # TODO: Move this to pre-signed URLs
        files_to_upload = data[_FILE_TO_UPLOADS_KEY]

        if len(files) != len(files_to_upload):
            raise ValueError(
                f"This endpoint is expecting {len(files_to_upload)} files to be uploaded. Found only {files}."
            )

        for file_to_upload in files_to_upload:
            upload_id = file_to_upload["upload_id"]
            name = file_to_upload["name"]
            url = f"{self.url}?upload_id={upload_id}"
            with open(files[name], "rb") as f:
                response = requests.post(url, files={upload_id: f})

            if response.status_code != 200:
                raise Exception(f"Failed to upload the file {name}. Status code: {response.status_code}")

    def _check_progress(self, data: Dict[str, str]) -> Dict[str, str]:
        """Check the current Studio status."""
        while True:
            url = f"{self.url}?run_id={data['run_id']}"
            response = requests.post(url)

            if response.status_code != 200:
                raise Exception(f"The file endpoint had an error. Status code: {response.status_code}")

            data = response.json()

            # Display the progress status to the user.
            print(data)

            if data["stage"] == "completed":
                break

            if data["stage"] == "failed":
                # TODO: Add more information on why the execution failed.
                raise RuntimeError("The Studio File Endpoint failed")

            # Wait until making the next request
            sleep(1)

        return data

    def _download_files(self, data: Dict[str, str], output_dir: str) -> None:
        """Download the artifact files."""
        os.makedirs(output_dir, exist_ok=True)

        for download_id in data[_DOWNLOAD_IDS_KEY]:
            url = f"{self.url}?download_id={download_id}"

            with requests.post(url, stream=True) as r:
                r.raise_for_status()
                filename = r.headers["Content-Disposition"].split("filename=")[1]
                filename = os.path.basename(filename)
                with open(os.path.join(output_dir, filename), "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
