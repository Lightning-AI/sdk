import json
import os
from time import sleep
from typing import Any, Dict, Optional
from uuid import uuid4

import requests

from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi import (
    CommandArgumentCommandArgumentType,
    ProjectIdServiceexecutionBody,
    V1CommandArgument,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.services.uploader import _ServiceFileUploader
from lightning_sdk.services.utilities import _get_project
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.utils import _resolve_teamspace

_FILE_TO_UPLOADS_KEY = "files_to_upload"
_DOWNLOAD_IDS_KEY = "download_ids"
_LIGHTNING_SERVICES_PIPELINE_ID = uuid4().hex


class FileEndpoint:
    # TODO: To be merged with the new Client
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


class Argument:
    """A holder for the service argument."""

    def __init__(self, name: str, type: CommandArgumentCommandArgumentType, **kwargs: Any) -> None:  # noqa: A002
        self._name = name
        self._type = type
        self._value = None
        self._kwargs = kwargs

    @property
    def is_text(self) -> bool:
        """Whether this argument is of type Text."""
        return self._type == CommandArgumentCommandArgumentType.TEXT

    @property
    def is_file(self) -> bool:
        """Whether this argument is of type File."""
        return self._type == CommandArgumentCommandArgumentType.FILE

    @property
    def value(self) -> Any:
        """Returns the value."""
        return self._value

    @value.setter
    def value(self, value: Any) -> None:
        """Store the value."""
        if self.is_file and not os.path.exists(value):
            raise ValueError(f"The argument {self._name} should be a valid file.")
        self._value = value

    @property
    def name(self) -> str:
        """Returns the name."""
        return self._name

    def to_openapi(self) -> V1CommandArgument:
        """Convert the argument into its OpenAPI dataclass counterpart."""
        if self.is_text:
            return V1CommandArgument(name=self._name, type=self._type, value=str(self._value))

        value = self._value.replace("/teamspace/studios/this_studio/", "")
        return V1CommandArgument(name=self._name, type=self._type, value=value)


class Client:
    """This class is used to communicate with the Service Endpoint."""

    def __init__(
        self,
        id: str,  # noqa: A002
        teamspace: Optional[str] = None,
    ) -> None:
        """Constructor of the FileEndpoint.

        Args:
            id: The id of the Studio File Endpoint Service.
            teamspace: The name of the Teamspace in which the Service

        """
        auth = Auth()

        try:
            auth.authenticate()
        except ConnectionError as e:
            raise e

        self.id = id

        self._client = LightningClient()
        if teamspace is not None:
            teamspace = _resolve_teamspace(teamspace, org=None, user=None)

        self._teamspace_id = (
            teamspace.id if isinstance(teamspace, Teamspace) else _get_project(client=self._client).project_id
        )

        self._file_endpoint = self._client.endpoint_service_get_file_endpoint(project_id=self._teamspace_id, id=self.id)
        self._arguments = []

        for argument in self._file_endpoint.arguments:
            self._arguments.append(Argument(**argument.to_dict()))

    def run(
        self,
        pipeline_id: Optional[str] = _LIGHTNING_SERVICES_PIPELINE_ID,
        download_artifacts: bool = True,
        **kwargs: Dict[str, str],
    ) -> None:
        """The run method executes the file endpoint.

        Args:
            pipeline_id: The ID of the current pipeline
            download_artifacts: Whether to download the artifacts associated to the service execution.
            kwargs: The keyword arguments associated to the service

        """
        for argument in self._arguments:
            if argument.is_file:
                if argument.name not in kwargs:
                    raise ValueError(f"This endpoint expects a file for the argument `{argument.name}`.")
                value = kwargs[argument.name]
                if not os.path.isfile(value):
                    raise ValueError(f"This endpoint expects a file for the argument `{argument.name}`.")
            else:
                if argument.name not in kwargs:
                    raise ValueError(f"This endpoint expects a value for the argument `{argument.name}`.")
                value = kwargs[argument.name]
                if os.path.isfile(value):
                    raise ValueError(f"This endpoint doesn't expect a file for `{argument.name}`.")

            argument.value = value

        missing_names = [v.name for v in self._arguments if v.value is None]
        if missing_names:
            raise ValueError(f"You are missing values for the following arguments: {missing_names}")

        service_execution = self._client.endpoint_service_create_service_execution(
            project_id=self._teamspace_id,
            body=ProjectIdServiceexecutionBody(
                file_endpoint_id=self.id,
                pipeline_id=pipeline_id,
                arguments=[argument.to_openapi() for argument in self._arguments],
            ),
        )

        for argument in self._arguments:
            if argument.is_text:
                continue

            upload_id = None
            for service_argument in service_execution.arguments:
                if argument.name == service_argument.name:
                    upload_id = service_argument.id

            if upload_id is None:
                raise ValueError("This shouldn't have happened. Please, contact lightning.ai.")

            # TODO: Move the logic to use pre-defined pre-signed URLs
            _ServiceFileUploader(
                client=self._client,
                teamspace_id=self._teamspace_id,
                service_execution_id=service_execution.id,
                upload_id=upload_id,
                file_path=argument.value,
                progress_bar=True,
            )()

        self._client.endpoint_service_run_service_execution(
            project_id=self._teamspace_id,
            id=service_execution.id,
            body={},
        )

        sleep(1)

        result = {}

        while True:
            service_execution_status = self._client.endpoint_service_get_service_execution_status(
                project_id=self._teamspace_id,
                id=service_execution.id,
                body={},
            )

            if "phase" in service_execution_status.data:
                phase = service_execution_status.data["phase"]

                if "FAILED" in phase:
                    print("Failed executing. Please, contact lightning.ai")
                    raise ValueError(f"Failed executing {service_execution.id}. Please, contact lightning.ai")

                if "COMPLETED" in phase:
                    if "result" in service_execution_status.data:
                        service_execution_status.data["result"] = json.loads(service_execution_status.data["result"])
                    print(service_execution_status)
                    break

            print(service_execution_status)

            sleep(3)

        if download_artifacts and "result" in service_execution_status.data:
            result = service_execution_status.data["result"]
            for k, v in result.items():
                print(k, v)
