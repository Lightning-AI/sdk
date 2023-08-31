import os
from typing import Optional, Generator, Dict

import tempfile
import tarfile

from urllib.parse import urlparse

import requests
import time

from lightning_cloud.login import Auth

from websockets.sync.client import connect, ClientConnection
import base64

from lightning.app.utilities.network import LightningClient

from lightning_cloud.openapi import IdCodeconfigBody, V1UserRequestedComputeConfig, V1GetCloudSpaceInstanceStatusResponse, V1CloudSpace, Externalv1CloudSpaceInstanceStatus, ProjectIdCloudspacesBody, CloudspaceIdRunsBody

from lightning_sdk.machine import Machine


class StudioApi:
    def __init__(self):
        super().__init__()

        self._client = LightningClient()

    def get_studio(
        self,
        name: str,
        teamspace_id: str,
    ) -> Optional[V1CloudSpace]:
        res = self._client.cloud_space_service_list_cloud_spaces(project_id=teamspace_id)
        _studio = [el for el in res.cloudspaces if el.display_name == name or el.name == name]
        if not _studio:
            # TODO: Let's use errors instead, reduces typing madness and less likely to accidentally get a None somewhere
            return None
        return _studio[0]

    def create_studio(
        self,
        name: str,
        teamspace_id: str,
        cluster: Optional[str] = None,
    ):
        body = ProjectIdCloudspacesBody(
            cluster_id=cluster,
            name=name,
            display_name=name,
        )
        studio = self._client.cloud_space_service_create_cloud_space(body, teamspace_id)

        run_body = CloudspaceIdRunsBody(
            cluster_id=cluster,
            local_source=True,
        )
        run = self._client.cloud_space_service_create_lightning_run(
            project_id=teamspace_id, cloudspace_id=studio.id, body=run_body
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            main_py_path = os.path.join(tmpdir, "main.py")
            main_py = open(main_py_path, "w")
            main_py.write("print('Hello, Lightning World!')\n")
            main_py.close()

            # TODO: Explore ways to do this without writing a file
            tar_path = os.path.join(tmpdir, "source.tar.gz")
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(main_py_path, arcname="main.py")
            
            with open(tar_path, "rb") as fo:
                requests.put(run.source_upload_url, data=fo)
        return studio

    def get_studio_status(self, studio_id: str, teamspace_id: str) -> V1GetCloudSpaceInstanceStatusResponse:
        res = self._client.cloud_space_service_get_cloud_space_instance_status(
            project_id=teamspace_id,
            id=studio_id,
        )
        return res

    def start_studio(self, studio_id: str, teamspace_id: str) -> None:
        auth_header = Auth().auth_header

        # TODO Have a constant and a fallback if not set
        cloud_url = os.environ.get("LIGHTNING_CLOUD_URL")
        code_url = f"{cloud_url}/v1/projects/{teamspace_id}/cloudspaces/{studio_id}/code/"

        while True:
            try:
                response = requests.get(code_url, headers={"Authorization": auth_header})
                response.raise_for_status()
                break
            except requests.HTTPError as e:
                time.sleep(1)
                continue

        while int(self.get_studio_status(studio_id, teamspace_id).in_use.startup_percentage) < 100:
            time.sleep(1)
    
    def stop_studio(self, studio_id: str, teamspace_id: str):
        # TODO: Wait for it to be stopped?
        self._client.cloud_space_service_stop_cloud_space_instance(
            project_id=teamspace_id,
            id=studio_id,
        )

    def switch_studio_machine(self, studio_id: str, teamspace_id: str, machine: Machine):
        compute_name = _MACHINE_TO_COMPUTE_NAME[machine]
        # TODO: UI sends disk size here, maybe we need to also?
        body = IdCodeconfigBody(compute_config=V1UserRequestedComputeConfig(name=compute_name))
        self._client.cloud_space_service_update_cloud_space_instance_config(
            id=studio_id,
            project_id=teamspace_id,
            body=body,
        )

        # TODO: Maybe strictly we need to wait for the machine to be running first?
        while int(self.get_studio_status(studio_id, teamspace_id).requested.startup_percentage) < 100:
            time.sleep(1)
        
        self._client.cloud_space_service_switch_cloud_space_instance(teamspace_id, studio_id)

    def run_studio_commands(self, studio_id: str, teamspace_id: str, *commands: str) -> Generator[str, None, None]:
        auth_header = Auth().auth_header

        cloud_url = os.environ.get("LIGHTNING_CLOUD_URL")
        parsed_cloud_url = urlparse(cloud_url)
        scheme = "wss" if parsed_cloud_url.scheme == "https" else "ws"
        terminal_url = f"{scheme}://{parsed_cloud_url.netloc}/v1/projects/{teamspace_id}/cloudspaces/{studio_id}/attach"

        command = "; ".join(commands)
        command = _wrap_command(command)
        command = f"{command}\n"

        websocket = connect(
            terminal_url,
            additional_headers = {
                "Authorization": auth_header
            },
        )

        # ignore any previous output
        _ = websocket.recv()

        websocket.send(command)

        return _read_output(websocket)


_BEGIN_OUTPUT_TOKEN = "LIGHTNING_BEGIN_OUTPUT"
_END_OUTPUT_TOKEN = "LIGHTNING_END_OUTPUT"


def _wrap_command(command: str) -> str:
    """Wrap a shell command to echo start and end tokens allowing us to parse the command output."""
    # We use escaped special characters here to differentiate between the tokens presence in the command vs the echoed output
    return f"echo \<\< {_BEGIN_OUTPUT_TOKEN} \>\>; {command}; echo \<\< {_END_OUTPUT_TOKEN} \>\>"

def _read_output(websocket: ClientConnection) -> Generator[str, None, None]:
    has_output_started = False
    begin_token = f"<< {_BEGIN_OUTPUT_TOKEN} >>"
    end_token = f"<< {_END_OUTPUT_TOKEN} >>"

    while True:
        websocket.ping()
        try:
            message = websocket.recv(timeout=10)
        except TimeoutError:
            continue

        if begin_token in message:
            has_output_started = True
            begin_index = message.rfind(begin_token) + len(begin_token)
            message = message[begin_index:].lstrip()

        if end_token in message:
            end_index = message.rfind(end_token)
            message = message[:end_index].rstrip()
            yield message
            break

        if has_output_started:
            yield message

    websocket.close()


# TODO: This should really come from some kind of metadata service
_MACHINE_TO_COMPUTE_NAME: Dict[Machine, str] = {
    Machine.CPU: "cpu-4",
    Machine.DATA_PREP: "data-large-8000",
    Machine.T4: "g4dn.2xlarge",
    Machine.T4_X_4: "g4dn.12xlarge",
    Machine.V100: "p3.2xlarge",
    Machine.V100_X_4: "p3.8xlarge",
    Machine.A10G: "g5.8xlarge",
    Machine.A10G_X_4: "g5.12xlarge",
    Machine.A100_X_8: "p4d.24xlarge",
}
