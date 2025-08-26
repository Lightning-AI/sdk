import json
import os
import time
from pathlib import Path
from threading import Event, Thread
from typing import Any, Dict, Generator, List, Mapping, Optional, Tuple, Union

import backoff
import requests
from tqdm import tqdm

from lightning_sdk.api.utils import (
    _create_app,
    _download_teamspace_files,
    _DummyBody,
    _DummyResponse,
    _FileUploader,
    _machine_to_compute_name,
    _sanitize_studio_remote_path,
)
from lightning_sdk.api.utils import (
    _get_cloud_url as _cloud_url,
)
from lightning_sdk.constants import _LIGHTNING_DEBUG
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi import (
    CloudspaceIdRunsBody,
    CloudspacesIdBody,
    Externalv1LightningappInstance,
    IdCodeconfigBody,
    IdExecuteBody1,
    IdForkBody1,
    IdSleepconfigBody,
    IdStartBody,
    ProjectIdCloudspacesBody,
    V1Assistant,
    V1CloudSpace,
    V1CloudSpaceInstanceConfig,
    V1CloudSpaceSeedFile,
    V1CloudSpaceSourceType,
    V1CloudSpaceState,
    V1ClusterAccelerator,
    V1EndpointType,
    V1EnvVar,
    V1GetCloudSpaceInstanceStatusResponse,
    V1GetLongRunningCommandInCloudSpaceResponse,
    V1LoginRequest,
    V1Plugin,
    V1PluginsListResponse,
    V1UpstreamCloudSpace,
    V1UserRequestedComputeConfig,
)
from lightning_sdk.lightning_cloud.openapi.models import ProjectIdEndpointsBody
from lightning_sdk.lightning_cloud.openapi.models.project_id_agentmanagedendpoints_body import (
    ProjectIdAgentmanagedendpointsBody,
)
from lightning_sdk.lightning_cloud.openapi.models.project_id_agents_body import (
    ProjectIdAgentsBody,
)
from lightning_sdk.lightning_cloud.openapi.models.v1_endpoint import V1Endpoint
from lightning_sdk.lightning_cloud.openapi.models.v1_managed_endpoint import V1ManagedEndpoint
from lightning_sdk.lightning_cloud.openapi.models.v1_managed_model import V1ManagedModel
from lightning_sdk.lightning_cloud.openapi.models.v1_upstream_managed import V1UpstreamManaged
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.machine import Machine


class StudioApi:
    """Internal API client for Studio requests (mainly http requests)."""

    def __init__(self) -> None:
        self._cloud_url = _cloud_url()
        self._client = LightningClient(max_tries=7)
        self._keep_alive_threads: Mapping[str, Thread] = {}
        self._keep_alive_events: Mapping[str, Event] = {}

    def start_keeping_alive(self, teamspace_id: str, studio_id: str) -> None:
        """Starts keeping the studio alive."""
        key = f"{teamspace_id}-{studio_id}"
        self._keep_alive_threads[key] = Thread(
            target=self._send_keepalives, kwargs={"teamspace_id": teamspace_id, "studio_id": studio_id}, daemon=True
        )
        self._keep_alive_events[key] = Event()
        self._keep_alive_threads[key].start()

    def stop_keeping_alive(self, teamspace_id: str, studio_id: str) -> None:
        """Stops keeping the studio alive."""
        key = f"{teamspace_id}-{studio_id}"

        if key in self._keep_alive_threads:
            self._keep_alive_events[key].set()
            self._keep_alive_threads[key].join()

    def _send_keepalives(self, teamspace_id: str, studio_id: str) -> None:
        """Sends keepalive requests as long as the event isn't set."""
        keep_alive_freq = os.environ.get("LIGHTNING_KEEPALIVE_FREQUENCY", 30)
        key = f"{teamspace_id}-{studio_id}"
        while not self._keep_alive_events[key].is_set():
            self._client.cloud_space_service_keep_alive_cloud_space_instance(
                body=_DummyBody(), project_id=teamspace_id, id=studio_id
            )
            time.sleep(keep_alive_freq)

    def get_studio(
        self,
        name: str,
        teamspace_id: str,
    ) -> V1CloudSpace:
        """Gets the current studio corresponding to the given name in the given teamspace."""
        res = self._client.cloud_space_service_list_cloud_spaces(project_id=teamspace_id, name=name)
        if not res.cloudspaces:
            raise ValueError(f"Studio {name} does not exist")
        return res.cloudspaces[0]

    def get_studio_by_id(
        self,
        studio_id: str,
        teamspace_id: str,
    ) -> V1CloudSpace:
        """Gets the current studio corresponding to the passed id."""
        return self._client.cloud_space_service_get_cloud_space(project_id=teamspace_id, id=studio_id)

    def create_studio(
        self,
        name: str,
        teamspace_id: str,
        cloud_account: Optional[str] = None,
        source: Optional[Union[V1CloudSpaceSourceType, str]] = None,
        disable_secrets: bool = False,
        sandbox: bool = False,
        cloud_space_environment_template_id: Optional[str] = None,
    ) -> V1CloudSpace:
        """Create a Studio with a given name in a given Teamspace on a possibly given cloud_account."""
        body = ProjectIdCloudspacesBody(
            cluster_id=cloud_account,
            name=name,
            display_name=name,
            seed_files=[V1CloudSpaceSeedFile(path="main.py", contents="print('Hello, Lightning World!')\n")],
            source=source,
            disable_secrets=disable_secrets,
            sandbox=sandbox,
            cloud_space_environment_template_id=cloud_space_environment_template_id,
        )
        studio = self._client.cloud_space_service_create_cloud_space(body, teamspace_id)

        run_body = CloudspaceIdRunsBody(
            cluster_id=studio.cluster_id,
            local_source=True,
        )
        _ = self._client.cloud_space_service_create_lightning_run(
            project_id=teamspace_id, cloudspace_id=studio.id, body=run_body
        )

        return studio

    def get_studio_status(self, studio_id: str, teamspace_id: str) -> V1GetCloudSpaceInstanceStatusResponse:
        """Gets the current (internal) Studio status."""
        return self._client.cloud_space_service_get_cloud_space_instance_status(
            project_id=teamspace_id,
            id=studio_id,
        )

    @backoff.on_exception(backoff.expo, AttributeError, max_tries=10)
    def _check_code_status_top_up_restore_finished(self, studio_id: str, teamspace_id: str) -> bool:
        """Retries checking the top_up_restore_finished value of the code status when there's an AttributeError."""
        if (
            self.get_studio_status(studio_id, teamspace_id) is None
            or self.get_studio_status(studio_id, teamspace_id).in_use is None
        ):
            return False
        startup_status = self.get_studio_status(studio_id, teamspace_id).in_use.startup_status
        return startup_status and startup_status.top_up_restore_finished

    def start_studio(
        self,
        studio_id: str,
        teamspace_id: str,
        machine: Union[Machine, str],
        interruptible: bool = False,
        max_runtime: Optional[int] = None,
    ) -> None:
        """Start an existing Studio."""
        # need to go via kwargs for typing compatibility since autogenerated apis accept None but aren't typed with None
        optional_kwargs_compute_body = {}

        if max_runtime is not None:
            optional_kwargs_compute_body["requested_run_duration_seconds"] = str(max_runtime)
        self._client.cloud_space_service_start_cloud_space_instance(
            IdStartBody(
                compute_config=V1UserRequestedComputeConfig(
                    name=_machine_to_compute_name(machine),
                    spot=interruptible,
                    **optional_kwargs_compute_body,
                )
            ),
            teamspace_id,
            studio_id,
        )

        while True:
            if self._check_code_status_top_up_restore_finished(studio_id, teamspace_id):
                break
            time.sleep(1)

        if _LIGHTNING_DEBUG:
            code_status = self.get_studio_status(studio_id, teamspace_id)
            instance_id = code_status.in_use.cloud_space_instance_id
            print(f"Studio started | {teamspace_id=} {studio_id=} {instance_id=}")

    def start_studio_async(
        self,
        studio_id: str,
        teamspace_id: str,
        machine: Union[Machine, str],
        interruptible: bool = False,
        max_runtime: Optional[int] = None,
    ) -> None:
        """Start an existing Studio without blocking."""
        # need to go via kwargs for typing compatibility since autogenerated apis accept None but aren't typed with None
        optional_kwargs_compute_body = {}

        if max_runtime is not None:
            optional_kwargs_compute_body["requested_run_duration_seconds"] = str(max_runtime)
        self._client.cloud_space_service_start_cloud_space_instance(
            IdStartBody(
                compute_config=V1UserRequestedComputeConfig(
                    name=_machine_to_compute_name(machine),
                    spot=interruptible,
                    **optional_kwargs_compute_body,
                )
            ),
            teamspace_id,
            studio_id,
        )

    def stop_studio(self, studio_id: str, teamspace_id: str) -> None:
        """Stop an existing Studio."""
        self.stop_keeping_alive(teamspace_id=teamspace_id, studio_id=studio_id)

        self._client.cloud_space_service_stop_cloud_space_instance(
            project_id=teamspace_id,
            id=studio_id,
        )

        # block until studio is really stopped
        while self._get_studio_instance_status(studio_id=studio_id, teamspace_id=teamspace_id) not in (
            None,
            "CLOUD_SPACE_INSTANCE_STATE_STOPPED",
        ):
            time.sleep(1)

    def _get_studio_instance_status(self, studio_id: str, teamspace_id: str) -> Optional[str]:
        """Returns status of the in-use instance of the Studio."""
        internal_status = self.get_studio_status(studio_id=studio_id, teamspace_id=teamspace_id).in_use
        if internal_status is None:
            return None

        return internal_status.phase

    def _get_studio_instance_status_from_object(self, studio: V1CloudSpace) -> Optional[str]:
        return getattr(getattr(studio.code_status, "in_use", None), "phase", None)

    def _request_switch(
        self, studio_id: str, teamspace_id: str, machine: Union[Machine, str], interruptible: bool
    ) -> None:
        """Switches given Studio to a new machine type."""
        compute_name = _machine_to_compute_name(machine)
        # TODO: UI sends disk size here, maybe we need to also?
        body = IdCodeconfigBody(compute_config=V1UserRequestedComputeConfig(name=compute_name, spot=interruptible))
        self._client.cloud_space_service_update_cloud_space_instance_config(
            id=studio_id,
            project_id=teamspace_id,
            body=body,
        )

    def switch_studio_machine(
        self, studio_id: str, teamspace_id: str, machine: Union[Machine, str], interruptible: bool
    ) -> None:
        """Switches given Studio to a new machine type."""
        self._request_switch(
            studio_id=studio_id, teamspace_id=teamspace_id, machine=machine, interruptible=interruptible
        )

        # Wait until it's time to switch
        requested_was_found = False
        startup_status = None
        while True:
            status = self.get_studio_status(studio_id, teamspace_id)
            requested_machine = status.requested

            if requested_machine is not None:
                requested_was_found = True
                startup_status = requested_machine.startup_status

            # if the requested machine was found in the past, use the in_use status instead.
            # it might be that it either was cancelled or it actually is ready.
            # Either way, since we're actually blocking below for the in use startup status
            # it's safe to switch at this point
            elif requested_was_found:
                in_use_machine = status.in_use
                if in_use_machine is not None:
                    startup_status = in_use_machine.startup_status

            if startup_status and startup_status.initial_restore_finished:
                break
            time.sleep(1)

        self._client.cloud_space_service_switch_cloud_space_instance(teamspace_id, studio_id)

        # Wait until the new machine is ready to use
        while True:
            in_use = self.get_studio_status(studio_id, teamspace_id).in_use
            if in_use is None:
                continue
            startup_status = in_use.startup_status
            if startup_status and startup_status.top_up_restore_finished:
                break
            time.sleep(1)

    def switch_studio_machine_with_progress(
        self,
        studio_id: str,
        teamspace_id: str,
        machine: Union[Machine, str],
        interruptible: bool,
        progress: Any,  # StudioProgressTracker - avoid circular import
    ) -> None:
        """Switches given Studio to a new machine type with progress tracking."""
        progress.update_progress(10, "Requesting machine switch...")

        self._request_switch(
            studio_id=studio_id, teamspace_id=teamspace_id, machine=machine, interruptible=interruptible
        )

        progress.update_progress(20, "Waiting for machine allocation...")

        # Wait until it's time to switch
        requested_was_found = False
        startup_status = None
        base_progress = 20
        max_wait_progress = 60
        wait_counter = 0

        while True:
            status = self.get_studio_status(studio_id, teamspace_id)
            requested_machine = status.requested

            if requested_machine is not None:
                requested_was_found = True
                startup_status = requested_machine.startup_status

            # if the requested machine was found in the past, use the in_use status instead.
            # it might be that it either was cancelled or it actually is ready.
            # Either way, since we're actually blocking below for the in use startup status
            # it's safe to switch at this point
            elif requested_was_found:
                in_use_machine = status.in_use
                if in_use_machine is not None:
                    startup_status = in_use_machine.startup_status

            if startup_status and startup_status.initial_restore_finished:
                break

            # Update progress gradually while waiting
            wait_counter += 1
            current_progress = min(base_progress + (wait_counter * 2), max_wait_progress)
            progress.update_progress(current_progress, "Allocating new machine...")
            time.sleep(1)

        progress.update_progress(70, "Starting machine switch...")
        self._client.cloud_space_service_switch_cloud_space_instance(teamspace_id, studio_id)

        progress.update_progress(80, "Configuring new machine...")

        # Wait until the new machine is ready to use
        switch_counter = 0
        while True:
            in_use = self.get_studio_status(studio_id, teamspace_id).in_use
            if in_use is None:
                continue
            startup_status = in_use.startup_status
            if startup_status and startup_status.top_up_restore_finished:
                break

            # Update progress while waiting for machine to be ready
            switch_counter += 1
            current_progress = min(80 + switch_counter, 95)
            progress.update_progress(current_progress, "Finalizing machine setup...")
            time.sleep(1)

        progress.complete("Machine switch completed successfully")

    def get_machine(self, studio_id: str, teamspace_id: str, cloud_account_id: str, org_id: str) -> Machine:
        """Get the current machine type the given Studio is running on."""
        response: V1CloudSpaceInstanceConfig = self._client.cloud_space_service_get_cloud_space_instance_config(
            project_id=teamspace_id, id=studio_id
        )
        accelerators = self._get_machines_for_cloud_account(
            teamspace_id=teamspace_id, cloud_account_id=cloud_account_id, org_id=org_id
        )

        for accelerator in accelerators:
            if response.compute_config.name in (
                accelerator.slug,
                accelerator.slug_multi_cloud,
                accelerator.instance_id,
            ):
                return Machine.from_str(accelerator.slug_multi_cloud)

        return Machine.from_str(response.compute_config.name)

    def get_interruptible(self, studio_id: str, teamspace_id: str) -> bool:
        """Get whether the Studio is running on a interruptible instance."""
        response: V1CloudSpaceInstanceConfig = self._client.cloud_space_service_get_cloud_space_instance_config(
            project_id=teamspace_id, id=studio_id
        )

        return response.compute_config.spot

    def _get_machines_for_cloud_account(
        self, teamspace_id: str, cloud_account_id: str, org_id: str
    ) -> List[V1ClusterAccelerator]:
        from lightning_sdk.api.cloud_account_api import CloudAccountApi

        cloud_account_api = CloudAccountApi()
        accelerators = cloud_account_api.list_cloud_account_accelerators(
            teamspace_id=teamspace_id,
            cloud_account_id=cloud_account_id,
            org_id=org_id,
        )
        if not accelerators:
            return []

        return list(filter(lambda acc: acc.enabled, accelerators.accelerator))

    def _get_detached_command_status(
        self, studio_id: str, teamspace_id: str, session_id: str
    ) -> V1GetLongRunningCommandInCloudSpaceResponse:
        """Get the status of a detached command."""
        # we need to decode this manually since this is ndjson and not usual json
        response_data = self._client.cloud_space_service_get_long_running_command_in_cloud_space_stream(
            project_id=teamspace_id, id=studio_id, session=session_id, _preload_content=False
        )

        if not response_data:
            raise RuntimeError("Unable to get status of running command")

        # convert from ndjson to json
        lines = ",".join(response_data.data.decode().splitlines())
        text = f"[{lines}]"
        # store in dummy class since api client deserializes the data attribute
        correct_response = _DummyResponse(text.encode())
        # decode as list of object as we have multiple of those
        responses = self._client.api_client.deserialize(
            correct_response, response_type="list[StreamResultOfV1GetLongRunningCommandInCloudSpaceResponse]"
        )

        for response in responses:
            yield response.result

    def run_studio_commands_and_yield(
        self, studio_id: str, teamspace_id: str, *commands: str, timeout: float, check_interval: float
    ) -> Generator[Tuple[str, int], None, None]:
        """Run given commands in a given Studio and yield the output and exit code for the given timeout.

        Args:
            timeout: wait for this many seconds for the command to finish.
        """
        response_submit = self._client.cloud_space_service_execute_command_in_cloud_space(
            IdExecuteBody1("; ".join(commands), detached=True),
            project_id=teamspace_id,
            id=studio_id,
        )

        if not response_submit:
            raise RuntimeError("Unable to submit command")

        if response_submit.session_name == "":
            raise RuntimeError("The session name should be defined.")

        start_time = time.time()
        exit_code = None
        while True:
            for resp in self._get_detached_command_status(
                studio_id=studio_id,
                teamspace_id=teamspace_id,
                session_id=response_submit.session_name,
            ):
                if time.time() - start_time >= timeout:
                    return

                if resp.exit_code == -1:
                    break

                if exit_code is None:
                    exit_code = resp.exit_code

                elif exit_code != resp.exit_code:
                    raise RuntimeError("Cannot determine exit code")

                if resp.exit_code is not None and resp.exit_code != 0:
                    raise RuntimeError(f"Command failed with exit code {resp.exit_code}. Output: {resp.output}")

                yield resp.output, exit_code
                time.sleep(check_interval)

    def run_studio_commands(self, studio_id: str, teamspace_id: str, *commands: str) -> Tuple[str, int]:
        """Run given commands in a given Studio."""
        response_submit = self._client.cloud_space_service_execute_command_in_cloud_space(
            IdExecuteBody1("; ".join(commands), detached=True),
            project_id=teamspace_id,
            id=studio_id,
        )

        if not response_submit:
            raise RuntimeError("Unable to submit command")

        if response_submit.session_name == "":
            raise RuntimeError("The session name should be defined.")

        while True:
            output = ""
            exit_code = None

            for resp in self._get_detached_command_status(
                studio_id=studio_id,
                teamspace_id=teamspace_id,
                session_id=response_submit.session_name,
            ):
                if resp.exit_code == -1:
                    break
                if exit_code is None:
                    exit_code = resp.exit_code
                elif exit_code != resp.exit_code:
                    raise RuntimeError("Cannot determine exit code")

                output += resp.output

            if exit_code is not None:
                return output, exit_code

            time.sleep(1)

    def update_autoshutdown(
        self,
        studio_id: str,
        teamspace_id: str,
        enabled: Optional[bool] = None,
        idle_shutdown_seconds: Optional[int] = None,
    ) -> V1CloudSpaceInstanceConfig:
        """Update the autoshutdown time and behaviour of the given Studio."""
        body = IdSleepconfigBody(
            disable_auto_shutdown=not enabled if enabled is not None else None,
            idle_shutdown_seconds=idle_shutdown_seconds,
        )
        return self._client.cloud_space_service_update_cloud_space_sleep_config(
            id=studio_id,
            project_id=teamspace_id,
            body=body,
        )

    def duplicate_studio(
        self, studio_id: str, teamspace_id: str, target_teamspace_id: str, machine: Machine = Machine.CPU
    ) -> Dict[str, Any]:
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
            IdForkBody1(target_project_id=target_teamspace_id), project_id=teamspace_id, id=studio_id
        )

        while self.get_studio_by_id(new_cloudspace.id, target_teamspace_id).state != V1CloudSpaceState.READY:
            time.sleep(1)

        init_kwargs["name"] = new_cloudspace.name
        init_kwargs["teamspace"] = target_teamspace.name

        self.start_studio(new_cloudspace.id, target_teamspace_id, machine, False, None)
        return init_kwargs

    def delete_studio(self, studio_id: str, teamspace_id: str) -> None:
        """Delete existing given Studio."""
        self.stop_keeping_alive(teamspace_id=teamspace_id, studio_id=studio_id)
        self._client.cloud_space_service_delete_cloud_space(project_id=teamspace_id, id=studio_id)

    def upload_file(
        self,
        studio_id: str,
        teamspace_id: str,
        cloud_account: str,
        file_path: str,
        remote_path: str,
        progress_bar: bool,
    ) -> None:
        """Uploads file to given remote path on the studio."""
        _FileUploader(
            client=self._client,
            teamspace_id=teamspace_id,
            cloud_account=cloud_account,
            file_path=file_path,
            remote_path=_sanitize_studio_remote_path(remote_path, studio_id),
            progress_bar=progress_bar,
        )()

    def download_file(
        self,
        path: str,
        target_path: str,
        studio_id: str,
        teamspace_id: str,
        cloud_account: str,
        progress_bar: bool = True,
    ) -> None:
        """Downloads a given file from a Studio to a target location."""
        # TODO: Update this endpoint to permit basic auth
        auth = Auth()
        auth.authenticate()
        token = self._client.auth_service_login(V1LoginRequest(auth.api_key)).token

        query_params = {
            "clusterId": cloud_account,
            "key": _sanitize_studio_remote_path(path, studio_id),
            "token": token,
        }

        r = requests.get(
            f"{self._client.api_client.configuration.host}/v1/projects/{teamspace_id}/artifacts/download",
            params=query_params,
            stream=True,
        )
        total_length = int(r.headers.get("content-length"))

        if progress_bar:
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

    def download_folder(
        self,
        path: str,
        target_path: str,
        studio_id: str,
        teamspace_id: str,
        cloud_account: str,
        progress_bar: bool = True,
    ) -> None:
        """Downloads a given folder from a Studio to a target location."""
        # TODO: implement resumable downloads
        auth = Auth()
        auth.authenticate()

        prefix = _sanitize_studio_remote_path(path, studio_id)
        # ensure we only download as a directory and not the entire prefix
        if prefix.endswith("/") is False:
            prefix = prefix + "/"

        _download_teamspace_files(
            client=self._client,
            teamspace_id=teamspace_id,
            cluster_id=cloud_account,
            prefix=prefix,
            download_dir=Path(target_path),
            progress_bar=progress_bar,
        )

    def install_plugin(self, studio_id: str, teamspace_id: str, plugin_name: str) -> str:
        """Installs the given plugin."""
        resp: V1Plugin = self._client.cloud_space_service_install_plugin(
            project_id=teamspace_id, id=studio_id, plugin_id=plugin_name
        )
        if not (resp.state == "installation_success" and resp.error == ""):
            raise RuntimeError(f"Failed to install plugin {plugin_name}: {resp.error}")

        additional_info = resp.additional_info or ""

        return additional_info.strip("\n").strip()

    def uninstall_plugin(self, studio_id: str, teamspace_id: str, plugin_name: str) -> None:
        """Uninstalls the given plugin."""
        resp: V1Plugin = self._client.cloud_space_service_uninstall_plugin(
            project_id=teamspace_id, id=studio_id, plugin_id=plugin_name
        )
        if not (resp.state == "uninstallation_success" and resp.error == ""):
            raise RuntimeError(f"Failed to uninstall plugin {plugin_name}: {resp.error}")

    def execute_plugin(self, studio_id: str, teamspace_id: str, plugin_name: str) -> Tuple[str, int]:
        """Executes the given plugin."""
        resp: V1Plugin = self._client.cloud_space_service_execute_plugin(
            project_id=teamspace_id, id=studio_id, plugin_id=plugin_name
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
        self,
        entrypoint: str,
        name: str,
        machine: Machine,
        studio_id: str,
        teamspace_id: str,
        cloud_account: str,
        interruptible: bool,
    ) -> Externalv1LightningappInstance:
        """Creates a job with given commands."""
        return self._create_app(
            studio_id=studio_id,
            teamspace_id=teamspace_id,
            cloud_account=cloud_account,
            plugin_type="job",
            entrypoint=entrypoint,
            name=name,
            compute=_machine_to_compute_name(machine),
            interruptible=interruptible,
        )

    def create_multi_machine_job(
        self,
        entrypoint: str,
        name: str,
        num_instances: int,
        machine: Machine,
        strategy: str,
        studio_id: str,
        teamspace_id: str,
        cloud_account: str,
        interruptible: bool,
    ) -> Externalv1LightningappInstance:
        """Creates a multi-machine job with given commands."""
        distributed_args = {
            "cloud_compute": _machine_to_compute_name(machine),
            "num_instances": num_instances,
            "strategy": strategy,
        }
        return self._create_app(
            studio_id=studio_id,
            teamspace_id=teamspace_id,
            cloud_account=cloud_account,
            plugin_type="distributed_plugin",
            entrypoint=entrypoint,
            name=name,
            distributedArguments=json.dumps(distributed_args),
            interruptible=interruptible,
        )

    def create_data_prep_machine_job(
        self,
        entrypoint: str,
        name: str,
        num_instances: int,
        machine: Machine,
        studio_id: str,
        teamspace_id: str,
        cloud_account: str,
        interruptible: bool,
    ) -> Externalv1LightningappInstance:
        """Creates a multi-machine job with given commands."""
        data_prep_args = {
            "cloud_compute": _machine_to_compute_name(machine),
            "num_instances": num_instances,
        }
        return self._create_app(
            studio_id=studio_id,
            teamspace_id=teamspace_id,
            cloud_account=cloud_account,
            plugin_type="litdata",
            entrypoint=entrypoint,
            name=name,
            dataPrepArguments=json.dumps(data_prep_args),
            interruptible=interruptible,
        )

    def create_inference_job(
        self,
        entrypoint: str,
        name: str,
        machine: Machine,
        min_replicas: str,
        max_replicas: str,
        max_batch_size: str,
        timeout_batching: str,
        scale_in_interval: str,
        scale_out_interval: str,
        endpoint: str,
        studio_id: str,
        teamspace_id: str,
        cloud_account: str,
        interruptible: bool,
    ) -> Externalv1LightningappInstance:
        """Creates an inference job for given endpoint."""
        return self._create_app(
            studio_id=studio_id,
            teamspace_id=teamspace_id,
            cloud_account=cloud_account,
            plugin_type="inference_plugin",
            compute=_machine_to_compute_name(machine),
            entrypoint=entrypoint,
            name=name,
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            max_batch_size=max_batch_size,
            timeout_batching=timeout_batching,
            scale_in_interval=scale_in_interval,
            scale_out_interval=scale_out_interval,
            endpoint=endpoint,
            interruptible=interruptible,
        )

    def start_new_port(self, teamspace_id: str, studio_id: str, name: str, port: int, auto_start: bool = False) -> str:
        """Starts a new port to the given Studio."""
        endpoint = self._client.endpoint_service_create_endpoint(
            project_id=teamspace_id,
            body=ProjectIdEndpointsBody(
                name=name,
                ports=[str(port)],
                cloudspace=V1UpstreamCloudSpace(
                    cloudspace_id=studio_id, port=str(port), type=V1EndpointType.PLUGIN_PORT, auto_start=auto_start
                ),
            ),
        )
        return endpoint.urls[0]

    def create_assistant(self, studio_id: str, teamspace_id: str, port: int, assistant_name: str) -> V1Assistant:
        target_teamspace = self._client.projects_service_get_project(teamspace_id)
        org_id = ""
        if target_teamspace.owner_type == "ORGANIZATION":
            org_id = target_teamspace.owner_id
        endpoint = self._client.endpoint_service_create_endpoint(
            project_id=teamspace_id,
            body=ProjectIdEndpointsBody(
                ports=[str(port)],
                cloudspace=V1UpstreamCloudSpace(
                    cloudspace_id=studio_id,
                    port=str(port),
                    type=V1EndpointType.PLUGIN_API,
                ),
            ),
        )
        valid_url = endpoint.urls[0]
        managed_endpoint = self._client.assistants_service_create_assistant_managed_endpoint(
            body=ProjectIdAgentmanagedendpointsBody(
                endpoint=V1ManagedEndpoint(
                    name=assistant_name,
                    base_url=valid_url + "/v1",
                    models_metadata=[
                        V1ManagedModel(
                            name=assistant_name,
                        )
                    ],
                ),
                org_id=org_id,
            ),
            project_id=teamspace_id,
        )

        body = ProjectIdAgentsBody(
            endpoint=V1Endpoint(
                cloudspace=V1UpstreamCloudSpace(cloudspace_id=studio_id),
                name=assistant_name,
                managed=V1UpstreamManaged(id=managed_endpoint.endpoint.id),
            ),
            name=assistant_name,
            model=assistant_name,
            cloudspace_id=studio_id,
            model_provider="",
        )

        return self._client.assistants_service_create_assistant(
            body=body,
            project_id=teamspace_id,
        )

    def _create_app(
        self, studio_id: str, teamspace_id: str, cloud_account: str, plugin_type: str, **other_arguments: Any
    ) -> Externalv1LightningappInstance:
        """Creates an arbitrary app."""
        return _create_app(
            self._client,
            studio_id=studio_id,
            teamspace_id=teamspace_id,
            cloud_account=cloud_account,
            plugin_type=plugin_type,
            **other_arguments,
        )

    def _update_cloudspace(self, studio: V1CloudSpace, teamspace_id: str, key: str, value: Any) -> None:
        body = CloudspacesIdBody(
            code_url=studio.code_url,
            data_connection_mounts=studio.data_connection_mounts,
            description=studio.description,
            display_name=studio.display_name,
            env=studio.env,
            featured=studio.featured,
            hide_files=studio.hide_files,
            is_cloudspace_private=studio.is_cloudspace_private,
            is_code_private=studio.is_code_private,
            is_favorite=studio.is_favorite,
            is_published=studio.is_published,
            license=studio.license,
            license_url=studio.license_url,
            message=studio.message,
            multi_user_edit=studio.multi_user_edit,
            operating_cost=studio.operating_cost,
            paper_authors=studio.paper_authors,
            paper_org=studio.paper_org,
            paper_org_avatar_url=studio.paper_org_avatar_url,
            paper_url=studio.paper_url,
            switch_to_default_machine_on_idle=studio.switch_to_default_machine_on_idle,
            tags=studio.tags,
            thumbnail_file_type=studio.thumbnail_file_type,
            user_metadata=studio.user_metadata,
        )

        setattr(body, key, value)

        self._client.cloud_space_service_update_cloud_space(
            id=studio.id,
            project_id=teamspace_id,
            body=body,
        )

    def set_env(
        self,
        studio: V1CloudSpace,
        teamspace_id: str,
        new_env: Dict[str, str],
        partial: bool = True,
    ) -> None:
        """Set the environment variables for the Studio.

        Args:
            new_env: The new environment variables to set.
            partial: Whether to only set the environment variables that are provided.
                If False, existing environment variables that are not in new_env will be removed.
                If True, existing environment variables that are not in new_env will be kept.
        """
        updated_env_dict = {}
        if partial:
            updated_env_dict = {env.name: env.value for env in studio.env}
            updated_env_dict.update(new_env)
        else:
            updated_env_dict = new_env

        updated_env = [V1EnvVar(name=key, value=value) for key, value in updated_env_dict.items()]

        self._update_cloudspace(studio, teamspace_id, "env", updated_env)

    def get_env(self, studio: V1CloudSpace) -> Dict[str, str]:
        return {env.name: env.value for env in studio.env}
