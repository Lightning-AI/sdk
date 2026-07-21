import concurrent
import json
import os
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Thread
from typing import Any, Dict, Generator, List, Mapping, Optional, Tuple, Union

import backoff
import requests
from tqdm import tqdm

from lightning_sdk.api.utils import (
    _authenticate_and_get_token,
    _BlobUploader,
    _create_app,
    _DummyBody,
    _DummyResponse,
    _machine_to_compute_name,
    _sanitize_studio_remote_path,
)
from lightning_sdk.api.utils import (
    _get_cloud_url as _cloud_url,
)
from lightning_sdk.constants import _LIGHTNING_DEBUG
from lightning_sdk.lightning_cloud.openapi import (
    AssistantsServiceCreateAssistantBody,
    AssistantsServiceCreateAssistantManagedEndpointBody,
    CloudSpaceServiceCreateCloudSpaceBody,
    CloudSpaceServiceCreateLightningRunBody,
    CloudSpaceServiceExecuteCommandInCloudSpaceBody,
    CloudSpaceServiceForkCloudSpaceBody,
    CloudSpaceServiceStartCloudSpaceInstanceBody,
    CloudSpaceServiceUpdateCloudSpaceBody,
    CloudSpaceServiceUpdateCloudSpaceInstanceConfigBody,
    CloudSpaceServiceUpdateCloudSpaceSleepConfigBody,
    EndpointServiceCreateEndpointBody,
    Externalv1LightningappInstance,
    V1Assistant,
    V1CloudSpace,
    V1CloudSpaceInstanceConfig,
    V1CloudSpaceSeedFile,
    V1CloudSpaceSourceType,
    V1CloudSpaceState,
    V1ClusterAccelerator,
    V1Endpoint,
    V1EndpointType,
    V1EnvVar,
    V1GetCloudSpaceInstanceStatusResponse,
    V1GetLongRunningCommandInCloudSpaceResponse,
    V1ManagedEndpoint,
    V1ManagedModel,
    V1UpstreamCloudSpace,
    V1UpstreamManaged,
    V1UserRequestedComputeConfig,
)
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
        """Starts keeping the studio alive.

        Args:
            teamspace_id: ID of the owning teamspace.
            studio_id: Studio (cloud space) ID to keep alive.
        """
        key = f"{teamspace_id}-{studio_id}"
        self._keep_alive_threads[key] = Thread(
            target=self._send_keepalives, kwargs={"teamspace_id": teamspace_id, "studio_id": studio_id}, daemon=True
        )
        self._keep_alive_events[key] = Event()
        self._keep_alive_threads[key].start()

    def stop_keeping_alive(self, teamspace_id: str, studio_id: str) -> None:
        """Stops keeping the studio alive.

        Args:
            teamspace_id: ID of the owning teamspace.
            studio_id: Studio (cloud space) ID to stop keeping alive.
        """
        key = f"{teamspace_id}-{studio_id}"

        if key in self._keep_alive_threads:
            self._keep_alive_events[key].set()
            self._keep_alive_threads[key].join()

    def _send_keepalives(self, teamspace_id: str, studio_id: str) -> None:
        """Sends keepalive requests as long as the event isn't set.

        Args:
            teamspace_id: ID of the owning teamspace.
            studio_id: Studio (cloud space) ID to send keepalives for.
        """
        keep_alive_freq = os.environ.get("LIGHTNING_KEEPALIVE_FREQUENCY", 30)
        key = f"{teamspace_id}-{studio_id}"
        while not self._keep_alive_events[key].is_set():
            self._client.cloud_space_service_keep_alive_cloud_space_instance(
                body=_DummyBody(), project_id=teamspace_id, id=studio_id
            )
            time.sleep(keep_alive_freq)

    def find_studio(
        self,
        name: str,
        teamspace_id: str,
    ) -> Optional[V1CloudSpace]:
        """Gets the studio corresponding to the given name in the given teamspace, if it exists.

        Args:
            name: Name of the Studio to look up.
            teamspace_id: ID of the owning teamspace.

        Returns:
            The matching ``V1CloudSpace`` object, or ``None`` if no Studio with the given name exists.
        """
        res = self._client.cloud_space_service_list_cloud_spaces(project_id=teamspace_id, name=name)
        return res.cloudspaces[0] if res.cloudspaces else None

    def get_studio(
        self,
        name: str,
        teamspace_id: str,
    ) -> V1CloudSpace:
        """Gets the current studio corresponding to the given name in the given teamspace.

        Args:
            name: Name of the Studio to look up.
            teamspace_id: ID of the owning teamspace.

        Returns:
            The matching ``V1CloudSpace`` object.

        Raises:
            ValueError: If no Studio with the given name exists in the teamspace.
        """
        studio = self.find_studio(name, teamspace_id)
        if studio is None:
            raise ValueError(f"Studio {name} does not exist")
        return studio

    def get_studio_by_id(
        self,
        studio_id: str,
        teamspace_id: str,
    ) -> V1CloudSpace:
        """Gets the current studio corresponding to the passed id.

        Args:
            studio_id: Studio (cloud space) ID to look up.
            teamspace_id: ID of the owning teamspace.

        Returns:
            The matching ``V1CloudSpace`` object.
        """
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
        """Create a Studio with a given name in a given Teamspace on a possibly given cloud_account.

        Args:
            name: Name for the new Studio.
            teamspace_id: ID of the owning teamspace.
            cloud_account: Optional cloud account (cluster) ID to create the Studio on.
            source: Optional source type for the Studio.
            disable_secrets: Whether to disable secrets for the Studio.
            sandbox: Whether to create the Studio in sandbox mode.
            cloud_space_environment_template_id: Optional environment template ID to apply.

        Returns:
            The created ``V1CloudSpace`` object.
        """
        body = CloudSpaceServiceCreateCloudSpaceBody(
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

        run_body = CloudSpaceServiceCreateLightningRunBody(
            cluster_id=studio.cluster_id,
            local_source=True,
        )
        _ = self._client.cloud_space_service_create_lightning_run(
            project_id=teamspace_id, cloudspace_id=studio.id, body=run_body
        )

        return studio

    def get_studio_status(self, studio_id: str, teamspace_id: str) -> V1GetCloudSpaceInstanceStatusResponse:
        """Gets the current (internal) Studio status.

        Args:
            studio_id: Studio (cloud space) ID.
            teamspace_id: ID of the owning teamspace.

        Returns:
            The ``V1GetCloudSpaceInstanceStatusResponse`` for the Studio.
        """
        return self._client.cloud_space_service_get_cloud_space_instance_status(
            project_id=teamspace_id,
            id=studio_id,
        )

    @backoff.on_exception(backoff.expo, AttributeError, max_tries=10)
    def _check_code_status_top_up_restore_finished(self, studio_id: str, teamspace_id: str) -> bool:
        """Retries checking the top_up_restore_finished value of the code status when there's an AttributeError.

        Args:
            studio_id: Studio (cloud space) ID.
            teamspace_id: ID of the owning teamspace.

        Returns:
            ``True`` if the top-up restore has finished, ``False`` otherwise.
        """
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
        """Start an existing Studio.

        Args:
            studio_id: Studio (cloud space) ID to start.
            teamspace_id: ID of the owning teamspace.
            machine: Machine type to start the Studio on.
            interruptible: Whether to use a spot (interruptible) instance.
            max_runtime: Optional maximum runtime in seconds before the Studio is stopped.
        """
        # need to go via kwargs for typing compatibility since autogenerated apis accept None but aren't typed with None
        optional_kwargs_compute_body = {}

        if max_runtime is not None:
            optional_kwargs_compute_body["requested_run_duration_seconds"] = str(max_runtime)
        self._client.cloud_space_service_start_cloud_space_instance(
            CloudSpaceServiceStartCloudSpaceInstanceBody(
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
        """Start an existing Studio without blocking.

        Args:
            studio_id: Studio (cloud space) ID to start.
            teamspace_id: ID of the owning teamspace.
            machine: Machine type to start the Studio on.
            interruptible: Whether to use a spot (interruptible) instance.
            max_runtime: Optional maximum runtime in seconds before the Studio is stopped.
        """
        # need to go via kwargs for typing compatibility since autogenerated apis accept None but aren't typed with None
        optional_kwargs_compute_body = {}

        if max_runtime is not None:
            optional_kwargs_compute_body["requested_run_duration_seconds"] = str(max_runtime)
        self._client.cloud_space_service_start_cloud_space_instance(
            CloudSpaceServiceStartCloudSpaceInstanceBody(
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
        """Stop an existing Studio.

        Args:
            studio_id: Studio (cloud space) ID to stop.
            teamspace_id: ID of the owning teamspace.
        """
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
        """Returns status of the in-use instance of the Studio.

        Args:
            studio_id: Studio (cloud space) ID.
            teamspace_id: ID of the owning teamspace.

        Returns:
            Phase string of the in-use instance, or ``None`` if no instance is running.
        """
        internal_status = self.get_studio_status(studio_id=studio_id, teamspace_id=teamspace_id).in_use
        if internal_status is None:
            return None

        return internal_status.phase

    def _get_studio_instance_status_from_object(self, studio: V1CloudSpace) -> Optional[str]:
        """Extract the running instance phase string from a studio object without a network call.

        Args:
            studio: The ``V1CloudSpace`` object to inspect.

        Returns:
            Phase string of the in-use instance, or ``None`` if not available.
        """
        return getattr(getattr(studio.code_status, "in_use", None), "phase", None)

    def _request_switch(
        self,
        studio_id: str,
        teamspace_id: str,
        machine: Union[Machine, str],
        interruptible: bool,
        cloud_account: Optional[str],
    ) -> None:
        """Switches given Studio to a new machine type.

        Args:
            studio_id: Studio (cloud space) ID to switch.
            teamspace_id: ID of the owning teamspace.
            machine: Target machine type.
            interruptible: Whether to use a spot (interruptible) instance.
            cloud_account: Optional cloud account ID to override the cluster.
        """
        compute_name = _machine_to_compute_name(machine)
        # TODO: UI sends disk size here, maybe we need to also?
        body = CloudSpaceServiceUpdateCloudSpaceInstanceConfigBody(
            compute_config=V1UserRequestedComputeConfig(name=compute_name, spot=interruptible)
        )
        if cloud_account:
            body.compute_config.cluster_override = cloud_account
        self._client.cloud_space_service_update_cloud_space_instance_config(
            id=studio_id,
            project_id=teamspace_id,
            body=body,
        )

    def switch_studio_machine(
        self,
        studio_id: str,
        teamspace_id: str,
        machine: Union[Machine, str],
        interruptible: bool,
        cloud_account: Optional[str],
    ) -> None:
        """Switches given Studio to a new machine type.

        Args:
            studio_id: Studio (cloud space) ID to switch.
            teamspace_id: ID of the owning teamspace.
            machine: Target machine type.
            interruptible: Whether to use a spot (interruptible) instance.
            cloud_account: Optional cloud account ID to override the cluster.
        """
        self._request_switch(
            studio_id=studio_id,
            teamspace_id=teamspace_id,
            machine=machine,
            interruptible=interruptible,
            cloud_account=cloud_account,
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
        cloud_account: Optional[str],
    ) -> None:
        """Switches given Studio to a new machine type with progress tracking.

        Args:
            studio_id: Studio (cloud space) ID to switch.
            teamspace_id: ID of the owning teamspace.
            machine: Target machine type.
            interruptible: Whether to use a spot (interruptible) instance.
            progress: Progress tracker object used to report switch stages.
            cloud_account: Optional cloud account ID to override the cluster.
        """
        progress.update_progress(10, "Requesting machine switch...")

        self._request_switch(
            studio_id=studio_id,
            teamspace_id=teamspace_id,
            machine=machine,
            interruptible=interruptible,
            cloud_account=cloud_account,
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

    def machine_is_supported(self, machine: Machine, teamspace_id: str, cloud_account_id: str, org_id: str) -> bool:
        """Check if the machine is available in provided cloud_account.

        Args:
            machine: Machine type to check availability for.
            teamspace_id: ID of the owning teamspace.
            cloud_account_id: Cloud account ID to check against.
            org_id: Organization ID required for cluster accelerator lookups.

        Returns:
            ``True`` if the machine type is available, ``False`` otherwise.
        """
        accelerators = self._get_machines_for_cloud_account(
            teamspace_id=teamspace_id, cloud_account_id=cloud_account_id, org_id=org_id
        )

        for accelerator in accelerators:
            if accelerator.accelerator_type == "GPU":
                accelerator_resources_count = accelerator.resources.gpu
            else:
                accelerator_resources_count = accelerator.resources.cpu
            if machine.accelerator_count == accelerator_resources_count and machine.family == accelerator.family:
                return True
        return False

    def machine_has_capacity(self, machine: Machine, teamspace_id: str, cloud_account_id: str, org_id: str) -> bool:
        """Check capacity of the requested machine.

        Args:
            machine: Machine type to check capacity for.
            teamspace_id: ID of the owning teamspace.
            cloud_account_id: Cloud account ID to check against.
            org_id: Organization ID required for cluster accelerator lookups.

        Returns:
            ``True`` if the machine has capacity, ``False`` if it is out of capacity.
        """
        accelerators = self._get_machines_for_cloud_account(
            teamspace_id=teamspace_id, cloud_account_id=cloud_account_id, org_id=org_id
        )

        for accelerator in accelerators:
            if accelerator.accelerator_type == "GPU":
                accelerator_resources_count = accelerator.resources.gpu
            else:
                accelerator_resources_count = accelerator.resources.cpu
            if (
                machine.accelerator_count == accelerator_resources_count
                and machine.family == accelerator.family
                and accelerator.out_of_capacity
            ):
                return False
        return True

    def get_machine(self, studio_id: str, teamspace_id: str, cloud_account_id: str, org_id: str) -> Machine:
        """Get the current machine type the given Studio is running on.

        Args:
            studio_id: Studio (cloud space) ID.
            teamspace_id: ID of the owning teamspace.
            cloud_account_id: Cloud account ID to look up accelerator details.
            org_id: Organization ID required for cluster accelerator lookups.

        Returns:
            The ``Machine`` instance corresponding to the Studio's current compute config.
        """
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
                return Machine._from_accelerator(accelerator)

        return Machine.from_str(response.compute_config.name)

    def get_interruptible(self, studio_id: str, teamspace_id: str) -> bool:
        """Get whether the Studio is running on a interruptible instance.

        Args:
            studio_id: Studio (cloud space) ID.
            teamspace_id: ID of the owning teamspace.

        Returns:
            ``True`` if the Studio is using a spot (interruptible) instance, ``False`` otherwise.
        """
        response: V1CloudSpaceInstanceConfig = self._client.cloud_space_service_get_cloud_space_instance_config(
            project_id=teamspace_id, id=studio_id
        )

        return response.compute_config.spot

    def get_public_ip(self, studio_id: str, teamspace_id: str) -> Optional[str]:
        """Get the public IP address of the Studio.

        Args:
            studio_id: Studio (cloud space) ID.
            teamspace_id: ID of the owning teamspace.

        Returns:
            The public IP address string, or ``None`` if the Studio has no running instance.
        """
        internal_status = self.get_studio_status(studio_id=studio_id, teamspace_id=teamspace_id).in_use
        if internal_status is None:
            return None

        return internal_status.public_ip_address

    def _get_machines_for_cloud_account(
        self, teamspace_id: str, cloud_account_id: str, org_id: str
    ) -> List[V1ClusterAccelerator]:
        """Return only the enabled accelerators for a given cloud account.

        Args:
            teamspace_id: ID of the owning teamspace.
            cloud_account_id: Cloud account ID to query accelerators for.
            org_id: Organization ID required for cluster accelerator lookups.

        Returns:
            List of enabled ``V1ClusterAccelerator`` objects for the cloud account.
        """
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
        """Get the status of a detached command.

        Args:
            studio_id: Studio (cloud space) ID the command is running in.
            teamspace_id: ID of the owning teamspace.
            session_id: Session name returned when the command was submitted.

        Returns:
            Generator yielding ``V1GetLongRunningCommandInCloudSpaceResponse`` result objects.

        Raises:
            RuntimeError: If the server returns an empty response.
        """
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
            studio_id: Studio (cloud space) ID to run the commands in.
            teamspace_id: ID of the owning teamspace.
            *commands: One or more shell commands to execute sequentially.
            timeout: Wait for this many seconds for the command to finish.
            check_interval: Seconds to wait between status poll requests.

        Returns:
            Generator yielding ``(output, exit_code)`` tuples as output becomes available.

        Raises:
            RuntimeError: If the command could not be submitted, the session name is missing,
                or the exit code is ambiguous across response chunks.
        """
        response_submit = self._client.cloud_space_service_execute_command_in_cloud_space(
            CloudSpaceServiceExecuteCommandInCloudSpaceBody("; ".join(commands), detached=True),
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
        """Run given commands in a given Studio.

        Args:
            studio_id: Studio (cloud space) ID to run the commands in.
            teamspace_id: ID of the owning teamspace.
            *commands: One or more shell commands to execute sequentially.

        Returns:
            Tuple of ``(combined_output, exit_code)`` after the commands finish.

        Raises:
            RuntimeError: If the command could not be submitted, the session name is missing,
                or the exit code is ambiguous across response chunks.
        """
        response_submit = self._client.cloud_space_service_execute_command_in_cloud_space(
            CloudSpaceServiceExecuteCommandInCloudSpaceBody("; ".join(commands), detached=True),
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
        """Update the autoshutdown time and behaviour of the given Studio.

        Args:
            studio_id: Studio (cloud space) ID to update.
            teamspace_id: ID of the owning teamspace.
            enabled: Whether auto-shutdown should be enabled. ``None`` leaves the current setting unchanged.
            idle_shutdown_seconds: Idle time in seconds before shutdown. ``None`` leaves unchanged.

        Returns:
            The updated ``V1CloudSpaceInstanceConfig`` object.
        """
        body = CloudSpaceServiceUpdateCloudSpaceSleepConfigBody(
            disable_auto_shutdown=not enabled if enabled is not None else None,
            idle_shutdown_seconds=idle_shutdown_seconds,
        )
        return self._client.cloud_space_service_update_cloud_space_sleep_config(
            id=studio_id,
            project_id=teamspace_id,
            body=body,
        )

    def duplicate_studio(
        self,
        studio_id: str,
        teamspace_id: str,
        target_teamspace_id: str,
        machine: Machine = Machine.CPU,
        new_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Duplicates the given Studio from a given Teamspace into a given target Teamspace.

        Args:
            studio_id: Studio (cloud space) ID to duplicate.
            teamspace_id: ID of the source teamspace.
            target_teamspace_id: ID of the target teamspace to fork the Studio into.
            machine: Machine type to start the duplicated Studio on.
            new_name: Optional name for the duplicated Studio; the original name is used if ``None``.

        Returns:
            Dict of keyword arguments suitable for re-initializing the duplicated Studio object.
        """
        target_teamspace = self._client.projects_service_get_project(target_teamspace_id)
        init_kwargs = {}
        if target_teamspace.owner_type == "user":
            from lightning_sdk.api.user_api import UserApi

            init_kwargs["user"] = UserApi()._get_user_by_id(target_teamspace.owner_id).username
        elif target_teamspace.owner_type == "organization":
            from lightning_sdk.api.org_api import OrgApi

            init_kwargs["org"] = OrgApi()._get_org_by_id(target_teamspace.owner_id).name

        new_cloudspace = self._client.cloud_space_service_fork_cloud_space(
            CloudSpaceServiceForkCloudSpaceBody(target_project_id=target_teamspace_id, new_name=new_name),
            project_id=teamspace_id,
            id=studio_id,
        )

        while self.get_studio_by_id(new_cloudspace.id, target_teamspace_id).state != V1CloudSpaceState.READY:
            time.sleep(1)

        init_kwargs["name"] = new_cloudspace.name
        init_kwargs["teamspace"] = target_teamspace.name

        self.start_studio(new_cloudspace.id, target_teamspace_id, machine, False, None)
        return init_kwargs

    def delete_studio(self, studio_id: str, teamspace_id: str) -> None:
        """Delete existing given Studio.

        Args:
            studio_id: Studio (cloud space) ID to delete.
            teamspace_id: ID of the owning teamspace.
        """
        self.stop_keeping_alive(teamspace_id=teamspace_id, studio_id=studio_id)
        self._client.cloud_space_service_delete_cloud_space(project_id=teamspace_id, id=studio_id)

    def get_tree(self, studio_id: str, teamspace_id: str, path: str, query_params: Optional[dict] = None) -> None:
        """Fetch the directory tree at ``path`` inside a Studio from the artifact REST API.

        Args:
            studio_id: Studio (cloud space) ID.
            teamspace_id: ID of the owning teamspace.
            path: Artifact path to inspect.
            query_params: Extra query parameters merged with the auth token.

        Returns:
            Parsed JSON response from the server.
        """
        token = _authenticate_and_get_token(self._client)

        if query_params is None:
            query_params = {
                "token": token,
            }
        else:
            query_params["token"] = token
        r = requests.get(
            f"{self._client.api_client.configuration.host}/v1/projects/{teamspace_id}/artifacts/cloudspaces/{studio_id}/trees/{path}",
            params=query_params,
        )
        return r.json()

    def get_path_info(self, studio_id: str, teamspace_id: str, path: str = "") -> dict:
        """Return existence, type, and size metadata for a path inside a Studio.

        Args:
            studio_id: Studio (cloud space) ID.
            teamspace_id: ID of the owning teamspace.
            path: Artifact path to check; empty string means root directory.

        Returns:
            Dict with keys ``exists`` (bool), ``type`` (``"file"``, ``"directory"``, or ``None``),
            and ``size`` (int bytes for files, ``None`` otherwise).
        """
        path = path.strip("/")

        if "/" in path:
            parent_path = path.rsplit("/", 1)[0]
            target_name = path.rsplit("/", 1)[1]
        else:
            if path == "":
                # root directory
                return {"exists": True, "type": "directory", "size": None}
            parent_path = ""
            target_name = path

        tree = self.get_tree(studio_id, teamspace_id, path=parent_path)
        tree_items = tree.get("tree", [])
        for item in tree_items:
            item_name = item.get("path", "")
            if item_name == target_name:
                item_type = item.get("type")
                # if type == "blob" it's a file, if "tree" it's a directory
                return {
                    "exists": True,
                    "type": "file" if item_type == "blob" else "directory",
                    "size": item.get("size", 0) if item_type == "blob" else None,
                }
        warnings.warn(f"If '{path}' is a directory, it may be empty and thus not detected.")
        return {"exists": False, "type": None, "size": None}

    def list_files(
        self,
        studio_id: str,
        teamspace_id: str,
        path: str = "",
    ) -> List[Dict]:
        """Recursively list all files in a directory tree.

        Args:
            studio_id: Studio (cloud space) ID.
            teamspace_id: ID of the owning teamspace.
            path: Root path inside the Studio to list; defaults to the root directory.

        Returns:
            List of file-info dicts from the recursive tree response.
        """
        path = path.strip("/")
        return self.get_tree(studio_id, teamspace_id, path, query_params={"recursive": "true"}).get("tree", [])

    def upload_file(
        self,
        studio_id: str,
        teamspace_id: str,
        cloud_account: str,
        file_path: str,
        remote_path: str,
        progress_bar: bool,
    ) -> None:
        """Uploads file to given remote path in the studio.

        Args:
            studio_id: Studio (cloud space) ID to upload the file into.
            teamspace_id: ID of the owning teamspace.
            cloud_account: Unused; the studio's cloud account determines storage.
            file_path: Local filesystem path of the file to upload.
            remote_path: Destination path inside the Studio.
            progress_bar: Whether to display a progress bar during upload.
        """
        # The remote path is relative to the Studio's content root.
        remote_path = remote_path.strip("/")

        client_host = self._client.api_client.configuration.host
        _BlobUploader(
            client=self._client,
            endpoint_base=f"{client_host}/v1/projects/{teamspace_id}/artifacts/cloudspaces/{studio_id}",
            file_path=file_path,
            remote_path=remote_path,
            progress_bar=progress_bar,
            notify_completion=True,
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
        """Downloads a given file from a Studio to a target location.

        Args:
            path: Path of the file inside the Studio to download.
            target_path: Local filesystem path to write the downloaded file to.
            studio_id: Studio (cloud space) ID containing the file.
            teamspace_id: ID of the owning teamspace.
            cloud_account: Cloud account ID used to locate the artifact.
            progress_bar: Whether to display a progress bar during download.

        Raises:
            RuntimeError: If the server returns a non-200 status code.
        """
        # TODO: Update this endpoint to permit basic auth
        token = _authenticate_and_get_token(self._client)

        query_params = {
            "clusterId": cloud_account,
            "key": _sanitize_studio_remote_path(path, studio_id),
            "token": token,
        }

        r = requests.get(
            f"{self._client.api_client.configuration.host}/v1/projects/{teamspace_id}/artifacts/cloudspaces/{studio_id}/blobs/{path}",
            params=query_params,
            stream=True,
            allow_redirects=True,
        )

        if r.status_code != 200:
            raise RuntimeError(f"Failed to download file: {r.status_code}")

        total_length = int(r.headers.get("content-length", 0))

        if progress_bar:
            pbar = tqdm(
                desc=f"Downloading {os.path.split(path)[1]}",
                total=total_length if total_length > 0 else None,
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

    def _download_single_studio_file(
        self,
        file_info: Dict,
        base_path: str,
        download_dir: Path,
        studio_id: str,
        teamspace_id: str,
        token: str,
        pbar: Optional[tqdm],
    ) -> None:
        """Download a single file from Studio with progress tracking.

        Args:
            file_info: Dict containing at least a ``"path"`` key with the file's artifact path.
            base_path: Base directory path prepended to the relative file path when building the request URL.
            download_dir: Local directory where the downloaded file is written.
            studio_id: Studio (cloud space) ID containing the file.
            teamspace_id: ID of the owning teamspace.
            token: Authentication token for the artifact API.
            pbar: Optional tqdm progress bar to update as bytes are written.
        """
        relative_path = file_info["path"].lstrip("/")
        local_file = download_dir / relative_path
        local_file.parent.mkdir(parents=True, exist_ok=True)

        file_path = os.path.join(base_path, relative_path) if base_path else relative_path

        query_params = {
            "token": token,
        }

        r = requests.get(
            f"{self._client.api_client.configuration.host}/v1/projects/{teamspace_id}/artifacts/cloudspaces/{studio_id}/blobs/{file_path}",
            params=query_params,
            stream=True,
        )

        with open(str(local_file), "wb") as f:
            for chunk in r.iter_content(chunk_size=4096 * 8):
                f.write(chunk)
                if pbar:
                    pbar.update(len(chunk))

    def download_folder(
        self,
        path: str,
        target_path: str,
        studio_id: str,
        teamspace_id: str,
        cloud_account: str,
        progress_bar: bool = True,
        num_workers: Optional[int] = None,
    ) -> None:
        """Downloads a given folder from a Studio to a target location.

        Args:
            path: Path of the folder inside the Studio to download.
            target_path: Local filesystem path to write the downloaded files to.
            studio_id: Studio (cloud space) ID containing the folder.
            teamspace_id: ID of the owning teamspace.
            cloud_account: Cloud account ID used to locate the artifacts.
            progress_bar: Whether to display a progress bar during download.
            num_workers: Number of parallel download threads; defaults to ``cpu_count * 4``.
        """
        # TODO: implement resumable downloads

        if num_workers is None:
            num_workers = os.cpu_count() * 4

        # Normalize the path
        path = path.strip("/")
        download_dir = Path(target_path)
        download_dir.mkdir(parents=True, exist_ok=True)

        files = self.list_files(studio_id, teamspace_id, path)

        if not files:
            print(f"No files found in {path}")
            return

        token = _authenticate_and_get_token(self._client)

        total_size = sum(f.get("size", 0) for f in files)

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
                    self._download_single_studio_file,
                    file_info,
                    path,
                    download_dir,
                    studio_id,
                    teamspace_id,
                    token,
                    pbar,
                )
                for file_info in files
            ]
            concurrent.futures.wait(futures)

        if pbar:
            pbar.set_description("Download complete")
            pbar.refresh()
            pbar.close()

    def remove_file(self, studio_id: str, teamspace_id: str, path: str) -> None:
        """Removes a file from a Studio.

        Args:
            studio_id: Studio (cloud space) ID containing the file.
            teamspace_id: ID of the owning teamspace.
            path: Path of the file to remove inside the Studio.

        Raises:
            FileNotFoundError: If the path does not exist in the Studio.
            IsADirectoryError: If the path points to a directory rather than a file.
            RuntimeError: If the server returns a non-204 status code.
        """
        info = self.get_path_info(studio_id, teamspace_id, path=path)

        if not info["exists"]:
            raise FileNotFoundError(f"The path '{path}' does not exist in the Studio.")

        if info["type"] != "file":
            raise IsADirectoryError(f"The path '{path}' is a directory. Use 'remove_folder()' to remove directories.")

        token = _authenticate_and_get_token(self._client)

        query_params = {"token": token}
        client_host = self._client.api_client.configuration.host
        url = f"{client_host}/v1/projects/{teamspace_id}/artifacts/cloudspaces/{studio_id}/blobs/{path}"

        r = requests.delete(url, params=query_params, timeout=30)

        if r.status_code == 204:
            return

        raise RuntimeError(f"Failed to remove file '{path}' from the Studio. Status code: {r.status_code}")

    def remove_folder(self, studio_id: str, teamspace_id: str, path: str) -> None:
        """Removes a folder (directory) from a Studio.

        Args:
            studio_id: Studio (cloud space) ID containing the folder.
            teamspace_id: ID of the owning teamspace.
            path: Path of the folder to remove inside the Studio.

        Raises:
            FileNotFoundError: If the path does not exist in the Studio.
            ValueError: If the path points to a file rather than a directory.
            RuntimeError: If the server returns a non-204 status code.
        """
        info = self.get_path_info(studio_id, teamspace_id, path=path)

        if not info["exists"]:
            raise FileNotFoundError(f"The path '{path}' does not exist in the Studio.")

        if info["type"] == "file":
            raise ValueError(f"The path '{path}' is a file. Use 'remove_file()' to remove files.")

        token = _authenticate_and_get_token(self._client)

        query_params = {"token": token}
        client_host = self._client.api_client.configuration.host
        url = f"{client_host}/v1/projects/{teamspace_id}/artifacts/cloudspaces/{studio_id}/trees/{path}"

        r = requests.delete(url, params=query_params, timeout=30)

        if r.status_code == 204:
            return

        raise RuntimeError(f"Failed to remove folder '{path}' from the Studio. Status code: {r.status_code}")

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
        """Creates a job with given commands.

        Args:
            entrypoint: Shell command or script path to run as the job entrypoint.
            name: Display name for the job.
            machine: Machine type to run the job on.
            studio_id: Studio (cloud space) ID associated with the job.
            teamspace_id: ID of the owning teamspace.
            cloud_account: Cloud account ID for the job's compute resources.
            interruptible: Whether to use a spot (interruptible) instance.

        Returns:
            The created ``Externalv1LightningappInstance`` representing the job.
        """
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
        """Creates a multi-machine job with given commands.

        Args:
            entrypoint: Shell command or script path to run as the job entrypoint.
            name: Display name for the job.
            num_instances: Number of machines to run in parallel.
            machine: Machine type for each instance.
            strategy: Distributed training strategy identifier.
            studio_id: Studio (cloud space) ID associated with the job.
            teamspace_id: ID of the owning teamspace.
            cloud_account: Cloud account ID for the job's compute resources.
            interruptible: Whether to use spot (interruptible) instances.

        Returns:
            The created ``Externalv1LightningappInstance`` representing the multi-machine job.
        """
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
        """Creates a multi-machine job with given commands.

        Args:
            entrypoint: Shell command or script path to run as the job entrypoint.
            name: Display name for the job.
            num_instances: Number of machines to run in parallel.
            machine: Machine type for each instance.
            studio_id: Studio (cloud space) ID associated with the job.
            teamspace_id: ID of the owning teamspace.
            cloud_account: Cloud account ID for the job's compute resources.
            interruptible: Whether to use spot (interruptible) instances.

        Returns:
            The created ``Externalv1LightningappInstance`` representing the data preparation job.
        """
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
        """Creates an inference job for given endpoint.

        Args:
            entrypoint: Shell command or script path to run as the inference server.
            name: Display name for the inference job.
            machine: Machine type to run the inference server on.
            min_replicas: Minimum number of replicas to keep running.
            max_replicas: Maximum number of replicas to scale up to.
            max_batch_size: Maximum request batch size per replica.
            timeout_batching: Maximum wait time in seconds to form a batch.
            scale_in_interval: Seconds of low traffic before scaling in.
            scale_out_interval: Seconds of high traffic before scaling out.
            endpoint: URL path prefix for the inference endpoint.
            studio_id: Studio (cloud space) ID associated with the job.
            teamspace_id: ID of the owning teamspace.
            cloud_account: Cloud account ID for the job's compute resources.
            interruptible: Whether to use spot (interruptible) instances.

        Returns:
            The created ``Externalv1LightningappInstance`` representing the inference job.
        """
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

    def add_port(self, teamspace_id: str, studio_id: str, name: str, port: int, auto_start: bool = False) -> V1Endpoint:
        """Starts a new port to the given Studio.

        Args:
            teamspace_id: ID of the owning teamspace.
            studio_id: Studio (cloud space) ID to expose the port on.
            name: Display name for the endpoint.
            port: Port number to expose.
            auto_start: Whether the endpoint should auto-start the Studio if stopped.

        Returns:
            The created ``V1Endpoint`` object.
        """
        return self._client.endpoint_service_create_endpoint(
            project_id=teamspace_id,
            body=EndpointServiceCreateEndpointBody(
                name=name,
                ports=[str(port)],
                cloudspace=V1UpstreamCloudSpace(
                    cloudspace_id=studio_id, port=str(port), type=V1EndpointType.PLUGIN_PORT, auto_start=auto_start
                ),
            ),
        )

    def get_port_url(
        self, teamspace_id: str, studio_id: str, port: Optional[int] = None, name: Optional[str] = None
    ) -> str:
        """Return the public URL for an exposed endpoint, looked up by port number or endpoint name.

        Args:
            teamspace_id: ID of the owning teamspace.
            studio_id: Studio (cloud space) ID.
            port: Port number to look up.
            name: Endpoint name to look up when ``port`` is not provided.

        Returns:
            The public URL string for the matching endpoint.

        Raises:
            ValueError: If neither argument is given, or no matching endpoint is found.
        """
        if port is None and name is None:
            raise ValueError("Either 'port' or 'name' must be provided")

        endpoints = self.list_ports(teamspace_id=teamspace_id, studio_id=studio_id)

        for endpoint in endpoints:
            if port is not None and port in endpoint.ports:
                idx = endpoint.ports.index(port)
                return endpoint.urls[idx]

            if name is not None and endpoint.name == name:
                return endpoint.urls[0] if endpoint.urls else None

        identifier = f"port {port}" if port else f"name '{name}'"
        raise ValueError(f"Endpoint with {identifier} not found")

    def list_ports(self, teamspace_id: str, studio_id: str) -> List[V1Endpoint]:
        """List ports that are exposed in the Studio.

        Args:
            teamspace_id: ID of the owning teamspace.
            studio_id: Studio (cloud space) ID to list endpoints for.

        Returns:
            List of ``V1Endpoint`` objects representing the exposed ports.
        """
        return self._client.endpoint_service_list_endpoints(
            project_id=teamspace_id,
            cloudspace_id=studio_id,
        ).endpoints

    def create_assistant(self, studio_id: str, teamspace_id: str, port: int, assistant_name: str) -> V1Assistant:
        """Create a managed AI assistant backed by a Studio's inference endpoint.

        Args:
            studio_id: Studio (cloud space) ID hosting the model server.
            teamspace_id: ID of the owning teamspace.
            port: Port on which the model server is listening.
            assistant_name: Display name for the created assistant.

        Returns:
            The created ``V1Assistant`` object.
        """
        target_teamspace = self._client.projects_service_get_project(teamspace_id)
        org_id = ""
        if target_teamspace.owner_type == "ORGANIZATION":
            org_id = target_teamspace.owner_id
        endpoint = self._client.endpoint_service_create_endpoint(
            project_id=teamspace_id,
            body=EndpointServiceCreateEndpointBody(
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
            body=AssistantsServiceCreateAssistantManagedEndpointBody(
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

        body = AssistantsServiceCreateAssistantBody(
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
        """Creates an arbitrary app.

        Args:
            studio_id: Studio (cloud space) ID to associate the app with.
            teamspace_id: ID of the owning teamspace.
            cloud_account: Cloud account ID for the app's compute resources.
            plugin_type: Plugin type identifier that determines the app kind.
            **other_arguments: Additional keyword arguments forwarded to the underlying app creator.

        Returns:
            The created ``Externalv1LightningappInstance``.
        """
        return _create_app(
            self._client,
            studio_id=studio_id,
            teamspace_id=teamspace_id,
            cloud_account=cloud_account,
            plugin_type=plugin_type,
            **other_arguments,
        )

    def _update_cloudspace(self, studio: V1CloudSpace, teamspace_id: str, key: str, value: Any) -> None:
        """Patch a single field on the cloudspace, keeping all other fields unchanged.

        Args:
            studio: The ``V1CloudSpace`` object whose current field values populate the update body.
            teamspace_id: ID of the owning teamspace.
            key: Name of the field to update on the cloudspace body.
            value: New value to set for the specified field.
        """
        body = CloudSpaceServiceUpdateCloudSpaceBody(
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
            studio: The ``V1CloudSpace`` object whose current env vars are used as the base.
            teamspace_id: ID of the owning teamspace.
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
        """Return the Studio's environment variables as a plain name → value dictionary.

        Args:
            studio: The ``V1CloudSpace`` object to read environment variables from.

        Returns:
            Dict mapping environment variable names to their values.
        """
        return {env.name: env.value for env in studio.env}
