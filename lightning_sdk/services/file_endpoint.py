import os
from pathlib import Path
from time import sleep
from typing import Any, Dict, Optional

import requests
import urllib3

from lightning_sdk.api.utils import _FileUploader
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.services.utilities import _get_cluster, _get_project, _get_service_url
from lightning_sdk.utils.resolve import _resolve_deprecated_cluster

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_LIGHTNING_SERVICE_EXECUTION_ID_HEADER = "X-Lightning-Service-Execution-Id"
_AUTHORIZATION_HEADER = "Authorization"


class Client:
    """This class is used to communicate with the File Endpoint."""

    def __init__(
        self,
        name: str,
        teamspace: Optional[str],
        cloud_account: Optional[str] = None,
        cluster_id: Optional[str] = None,  # deprecated in favor of cloud_account
    ) -> None:
        """Constructor of the Client.

        Args:
            name: The name of the Studio File Endpoint Service.
            teamspace: The name of the teamspace you want to attach the upload data and artifacts to be.
            cloud_account: The name of the cloud account on which to upload the data.

        """
        cloud_account = _resolve_deprecated_cluster(cloud_account, cluster_id)

        self._auth = Auth()

        try:
            self._auth.authenticate()
        except ConnectionError as e:
            raise e

        self._name = name
        self._teamspace = teamspace
        self._client = LightningClient()
        self._project = _get_project(client=self._client, project_name=teamspace)
        self._cloud_account = _get_cluster(
            client=self._client, project_id=self._project.project_id, cluster_id=cloud_account
        )
        self._file_endpoint = self._client.endpoint_service_get_file_endpoint_by_name(
            project_id=self._project.project_id, name=self._name
        )

        self.headers = {_AUTHORIZATION_HEADER: f"Bearer {self._auth.api_key}"}

        self._arguments = []
        for argument in self._file_endpoint.arguments:
            self._arguments.append(Argument(**argument.to_dict()))

        self.url = _get_service_url(self._file_endpoint.cloudspace_id, self._file_endpoint.id)

    def run(
        self,
        **kwargs: Dict[str, str],
    ) -> None:
        """The run method executes the file endpoint.

        Args:
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

            argument.value = str(Path(value).resolve())

        missing_names = [v.name for v in self._arguments if v.value is None]
        if missing_names:
            raise ValueError(f"You are missing values for the following arguments: {missing_names}")

        # Avoid uploading duplicated files
        files_to_upload = {}
        for argument in self._arguments:
            if not argument.should_upload:
                continue
            files_to_upload[argument.value] = argument

        # TODO: Verify if the file exists in Teampace and avoid uploading if already there.
        for argument in files_to_upload.values():
            _FileUploader(
                client=self._client,
                teamspace_id=self._project.project_id,
                cloud_account=self._cloud_account.cluster_id,
                file_path=argument.value,
                progress_bar=True,
                remote_path=_sanitize_uploads_remote_path(argument.value),
            )()

        json = {
            "teamspace_id": self._project.project_id,
            "cluster_id": self._cloud_account.cluster_id,
            "input": {},
        }
        for argument in self._arguments:
            json["input"].update(**argument.to_dict())

        response = requests.post(self.url, json=json, headers=self.headers)
        if response.status_code != 200:
            raise Exception(f"The endpoint isn't reachable. Status code: {response.status_code}")

        self.headers = {
            **self.headers,
            _LIGHTNING_SERVICE_EXECUTION_ID_HEADER: response.headers[_LIGHTNING_SERVICE_EXECUTION_ID_HEADER],
        }

        self._check_progress(response.json())

    def _check_progress(self, data: Dict[str, str]) -> Dict[str, str]:
        """Check the current Studio status."""
        while True:
            url = f"{self.url}?run_id={data['run_id']}"
            response = requests.post(url, headers=self.headers)

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
            sleep(3)

        return data


class Argument:
    """A holder for the service argument."""

    def __init__(self, name: str, type: str, **kwargs: Any) -> None:  # noqa: A002
        self._name = name
        self._type = type
        self._value = None
        self._kwargs = kwargs

    @property
    def is_text(self) -> bool:
        """Whether this argument is of type Text."""
        return self._type == "Text"

    @property
    def is_file(self) -> bool:
        """Whether this argument is of type File."""
        return self._type == "File"

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

    def to_dict(self) -> Dict[str, str]:
        """Convert the argument into its OpenAPI dataclass counterpart."""
        if self.is_text:
            return {self._name: str(self._value)}

        if self.should_upload:
            return {self._name: f"/teamspace/Uploads/{os.path.basename(self._value)}"}

        return {self._name: self._value}

    @property
    def should_upload(self) -> bool:
        """Whether the file should be uploaded."""
        if not self.is_file:
            return False

        value = str(Path(self.value).resolve())
        if value.startswith("/teamspace/"):
            return False

        return True


def _sanitize_uploads_remote_path(file_path: str) -> str:
    remote_path = os.path.basename(file_path)
    return f"/Uploads/{remote_path}"
