import os
import tarfile
import tempfile
import time
from typing import Any, Dict, Optional, Tuple

import requests
from lightning_cloud.openapi import (
    CloudspaceIdRunsBody,
    Externalv1LightningappInstance,
    IdCodeconfigBody,
    IdExecuteBody,
    IdForkBody,
    ProjectIdCloudspacesBody,
    V1CloudSpace,
    V1CloudSpaceInstanceConfig,
    V1GetCloudSpaceInstanceStatusResponse,
    V1Plugin,
    V1PluginsListResponse,
    V1UserRequestedComputeConfig,
)

try:
    from lightning_cloud.openapi import AppsIdBody1 as AppsIdBody
except ImportError:
    from lightning_cloud.openapi import AppsIdBody

import json

from lightning_cloud.rest_client import LightningClient

from lightning_sdk.machine import Machine


class StudioApi:
    """Internal API client for Studio requests (mainly http requests)."""

    def __init__(self) -> None:
        super().__init__()

        self._cloud_url = _cloud_url()
        self._client = LightningClient()

    def get_studio(
        self,
        name: str,
        teamspace_id: str,
    ) -> V1CloudSpace:
        """Gets the current studio corresponding to the given name in the given teamspace."""
        res = self._client.cloud_space_service_list_cloud_spaces(project_id=teamspace_id)
        _studio = [el for el in res.cloudspaces if el.display_name == name or el.name == name]
        if not _studio:
            raise ValueError(f"Studio {name} does not exist")
        return _studio[0]

    def create_studio(
        self,
        name: str,
        teamspace_id: str,
        cluster: Optional[str] = None,
    ) -> V1CloudSpace:
        """Create a Studio with a given name in a given Teamspace on a possibly given cluster."""
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
            with open(main_py_path, "w") as f:
                f.write("print('Hello, Lightning World!')\n")

            # TODO: Explore ways to do this without writing a file
            tar_path = os.path.join(tmpdir, "source.tar.gz")
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(main_py_path, arcname="main.py")

            with open(tar_path, "rb") as fo:
                requests.put(run.source_upload_url, data=fo)
        return studio

    def get_studio_status(self, studio_id: str, teamspace_id: str) -> V1GetCloudSpaceInstanceStatusResponse:
        """Gets the current (internal) Studio status."""
        return self._client.cloud_space_service_get_cloud_space_instance_status(
            project_id=teamspace_id,
            id=studio_id,
        )

    def start_studio(self, studio_id: str, teamspace_id: str) -> None:
        """Start an existing Studio."""
        self._client.cloud_space_service_start_cloud_space_instance(teamspace_id, studio_id)

        while self.get_studio_status(studio_id, teamspace_id).in_use.sync_in_progress:
            time.sleep(1)

        while int(self.get_studio_status(studio_id, teamspace_id).in_use.startup_percentage) < 100:
            time.sleep(1)

    def stop_studio(self, studio_id: str, teamspace_id: str) -> None:
        """Stop an existing Studio."""
        # TODO: Wait for it to be stopped? This would match the time a user actually pays for an instance then
        self._client.cloud_space_service_stop_cloud_space_instance(
            project_id=teamspace_id,
            id=studio_id,
        )

    def switch_studio_machine(self, studio_id: str, teamspace_id: str, machine: Machine) -> None:
        """Switches given Studio to a new machine type."""
        compute_name = _MACHINE_TO_COMPUTE_NAME[machine]
        # TODO: UI sends disk size here, maybe we need to also?
        body = IdCodeconfigBody(compute_config=V1UserRequestedComputeConfig(name=compute_name))
        self._client.cloud_space_service_update_cloud_space_instance_config(
            id=studio_id,
            project_id=teamspace_id,
            body=body,
        )

        while int(self.get_studio_status(studio_id, teamspace_id).requested.startup_percentage) < 100:
            time.sleep(1)

        self._client.cloud_space_service_switch_cloud_space_instance(teamspace_id, studio_id)

    def get_machine(self, studio_id: str, teamspace_id: str) -> Machine:
        """Get the current machine type the given Studio is running on."""
        response: V1CloudSpaceInstanceConfig = self._client.cloud_space_service_get_cloud_space_instance_config(
            project_id=teamspace_id, id=studio_id
        )
        return _COMPUTE_NAME_TO_MACHINE[response.compute_config.name]

    def run_studio_commands(self, studio_id: str, teamspace_id: str, *commands: str) -> Tuple[str, int]:
        """Run given commands in a given Studio."""
        response = self._client.cloud_space_service_execute_command_in_cloud_space(
            IdExecuteBody("; ".join(commands)), project_id=teamspace_id, id=studio_id
        )
        return response.output, response.exit_code

    def duplicate_studio(self, studio_id: str, teamspace_id: str, target_teamspace_id: str) -> Dict[str, str]:
        """Duplicates the given Studio from a given Teamspace into a given target Teamspace."""
        target_teamspace = self._client.projects_service_get_project(target_teamspace_id)
        init_kwargs = {}
        if target_teamspace.owner_type == "user":
            from lightning_sdk.api.user_api import UserApi

            init_kwargs["user"] = UserApi()._get_user_by_id(target_teamspace.owner_id).username
        elif target_teamspace.owner_type == "organization":
            from lightning_sdk.api.org_api import OrgApi

            init_kwargs["org"] = OrgApi()._get_org_by_id(target_teamspace.owner_id).name

        new_cloudspace = self._client.cloud_space_service_fork_cloud_space(
            IdForkBody(target_project_id=target_teamspace_id), project_id=teamspace_id, id=studio_id
        )

        init_kwargs["name"] = new_cloudspace.name
        init_kwargs["teamspace"] = target_teamspace.name

        self.start_studio(new_cloudspace.id, target_teamspace_id)
        return init_kwargs

    def delete_studio(self, studio_id: str, teamspace_id: str) -> None:
        """Delete existing given Studio."""
        self._client.cloud_space_service_delete_cloud_space(project_id=teamspace_id, id=studio_id)

    def install_plugin(self, studio_id: str, teamspace_id: str, plugin_name: str) -> str:
        """Installs the given plugin."""
        resp: V1Plugin = self._client.cloud_space_service_install_plugin(
            project_id=teamspace_id, id=studio_id, plugin_id=plugin_name
        )
        if not (resp.state == "installation_success" and resp.error == ""):
            raise RuntimeError(f"Failed to install plugin {plugin_name}: {resp.error}")

        return resp.additional_info.strip("\n").strip()

    def uninstall_plugin(self, studio_id: str, teamspace_id: str, plugin_name: str) -> None:
        """Uninstalls the given plugin."""
        resp: V1Plugin = self._client.cloud_space_service_uninstall_plugin(
            project_id=teamspace_id, id=studio_id, plugin_id=plugin_name
        )
        if not (resp.state == "uninstallation_success" and resp.error == ""):
            raise RuntimeError(f"Failed to uninstall plugin {plugin_name}: {resp.error}")

    def execute_plugin(self, studio_id: str, teamspace_id: str, plugin_name: str) -> str:
        """Executes the given plugin."""
        resp: V1Plugin = self._client.cloud_space_service_execute_plugin(
            roject_id=teamspace_id, id=studio_id, plugin_id=plugin_name
        )
        if not (resp.state == "execution_success" and resp.error == ""):
            raise RuntimeError(f"Failed to execute plugin {plugin_name}: {resp.error}")

        additional_info_string = resp.additional_info
        additional_info = json.loads(additional_info_string)
        port = int(additional_info["port"])

        output_str = ""

        # if port is specified greater than 0 this means the plugin is interactive.
        # Prompt the user to head to the browser
        if port > 0:
            output_str = (
                f"Plugin {plugin_name} is interactive. Have a look at https://{port}-{studio_id}.cloudspaces.litng.ai"
            )

        elif port < 0:
            output_str = "This plugin can only be used on the browser interface of a Studio!"

        # TODO: retrieve actual command output?
        elif port == 0:
            output_str = f"Successfully executed plugin {plugin_name}"

        return output_str, port

    def list_available_plugins(self, studio_id: str, teamspace_id: str) -> Dict[str, str]:
        """Lists the available plugins."""
        resp: V1PluginsListResponse = self._client.cloud_space_service_list_available_plugins(
            project_id=teamspace_id, id=studio_id
        )
        return resp.plugins

    def list_installed_plugins(self, studio_id: str, teamspace_id: str) -> Dict[str, str]:
        """Lists all installed plugins."""
        resp: V1PluginsListResponse = self._client.cloud_space_service_list_installed_plugins(
            project_id=teamspace_id, id=studio_id
        )
        return resp.plugins

    def create_job(
        self, entrypoint: str, name: str, cloud_compute: Machine, studio_id: str, teamspace_id: str, cluster_id: str
    ) -> Externalv1LightningappInstance:
        """Creates a job with given commands."""
        return self._create_app(
            studio_id=studio_id,
            teamspace_id=teamspace_id,
            cluster_id=cluster_id,
            plugin_type="job",
            entrypoint=entrypoint,
            name=name,
            compute=_MACHINE_TO_COMPUTE_NAME[cloud_compute],
        )

    def create_multi_machine_job(
        self,
        entrypoint: str,
        name: str,
        num_instances: int,
        cloud_compute: Machine,
        strategy: str,
        studio_id: str,
        teamspace_id: str,
        cluster_id: str,
    ) -> Externalv1LightningappInstance:
        """Creates a multi-machine job with given commands."""
        distributed_args = {
            "cloud_compute": _MACHINE_TO_COMPUTE_NAME[cloud_compute],
            "num_instances": num_instances,
            "strategy": strategy,
        }
        return self._create_app(
            studio_id=studio_id,
            teamspace_id=teamspace_id,
            cluster_id=cluster_id,
            plugin_type="distributed_plugin",
            entrypoint=entrypoint,
            name=name,
            distributedArguments=json.dumps(distributed_args),
        )

    def create_inference_job(
        self,
        entrypoint: str,
        name: str,
        cloud_compute: Machine,
        min_replicas: str,
        max_replicas: str,
        max_batch_size: str,
        timeout_batching: str,
        scale_in_interval: str,
        scale_out_interval: str,
        endpoint: str,
        studio_id: str,
        teamspace_id: str,
        cluster_id: str,
    ) -> Externalv1LightningappInstance:
        """Creates an inference job for given endpoint."""
        return self._create_app(
            studio_id=studio_id,
            teamspace_id=teamspace_id,
            cluster_id=cluster_id,
            plugin_type="inference_plugin",
            compute=_MACHINE_TO_COMPUTE_NAME[cloud_compute],
            entrypoint=entrypoint,
            name=name,
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            max_batch_size=max_batch_size,
            timeout_batching=timeout_batching,
            scale_in_inverval=scale_in_interval,
            scale_out_interval=scale_out_interval,
            endpoint=endpoint,
        )

    def _create_app(
        self, studio_id: str, teamspace_id: str, cluster_id: str, plugin_type: str, **other_arguments: Any
    ) -> Externalv1LightningappInstance:
        """Creates an arbitrary app."""
        body = AppsIdBody(cluster_id=cluster_id, plugin_arguments=other_arguments)

        return self._client.cloud_space_service_create_cloud_space_app_instance(
            body=body, project_id=teamspace_id, cloudspace_id=studio_id, id=plugin_type
        )


def _cloud_url() -> str:
    # set cloud url with default url if not set before
    cloud_url = os.environ.get("LIGHTNING_CLOUD_URL", _DEFAULT_CLOUD_URL)
    os.environ["LIGHTNING_CLOUD_URL"] = cloud_url
    return cloud_url


# TODO: This should really come from some kind of metadata service
# TODO: Add trainium instances once feature flag is lifted
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

_COMPUTE_NAME_TO_MACHINE: Dict[str, Machine] = {v: k for k, v in _MACHINE_TO_COMPUTE_NAME.items()}

_DEFAULT_CLOUD_URL = "https://lightning.ai:443"
