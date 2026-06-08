import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import requests

from lightning_sdk.api import CloudAccountApi, UserApi
from lightning_sdk.api.deployment_api import (
    ApiKeyAuth,
    Auth,
    AutoScaleConfig,
    BasicAuth,
    DateTimeLike,
    DeploymentApi,
    Env,
    ExecHealthCheck,
    HttpHealthCheck,
    PathLike,
    ReleaseStrategy,
    RequestCaptureExportResult,
    Secret,
    TokenAuth,
    compose_commands,
    restore_auth,
    restore_autoscale,
    restore_env,
    restore_health_check,
    restore_release_strategy,
    to_autoscaling,
    to_byom_spec,
    to_endpoint,
    to_spec,
    to_strategy,
)
from lightning_sdk.api.utils import AccessibleResource, raise_access_error_if_not_allowed
from lightning_sdk.lightning_cloud import login
from lightning_sdk.lightning_cloud.openapi import V1Deployment
from lightning_sdk.machine import CloudProvider, Machine
from lightning_sdk.organization import Organization
from lightning_sdk.services.utilities import _get_cluster
from lightning_sdk.studio import Studio
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User
from lightning_sdk.utils.logging import TrackCallsMeta
from lightning_sdk.utils.resolve import (
    _resolve_default_cloud_account,
    _resolve_org,
    _resolve_teamspace,
    _resolve_user,
    _warn_deprecated_cloud_selection,
)


class Deployment(metaclass=TrackCallsMeta):
    """The Lightning AI Deployment.

    Allows to fully control a deployment, including retrieving the status, making new release
    and switching machine types, etc..

    Args:
        name: The name or the id of the deployment.
        teamspace: The teamspace in which you want to deploy.
        org: The name of the organization owning the :param`teamspace` in case it is owned by an org
        user: The name of the user owning the :param`teamspace` in case it is owned directly by a user instead of an org

    Note:
        Since a teamspace can either be owned by an org or by a user directly,
        only one of the arguments can be provided.

    """

    def __init__(
        self,
        name: Optional[str] = None,
        teamspace: Optional[Union[str, Teamspace]] = None,
        org: Optional[Union[str, Organization]] = None,
        user: Optional[Union[str, User]] = None,
    ) -> None:
        self._request_session = None
        self._cloud_account_api = CloudAccountApi()

        self._auth = login.Auth()
        self._user = None

        try:
            self._auth.authenticate()
            if user is None:
                self._user = User(name=UserApi()._get_user_by_id(self._auth.user_id).username)
        except ConnectionError as e:
            raise e

        if name is None:
            name = "dep_" + datetime.now().strftime("%m-%d_%H:%M:%S")

        self._name = name
        self._user = _resolve_user(self._user or user)
        self._org = _resolve_org(org)

        self._teamspace = _resolve_teamspace(
            teamspace=teamspace,
            org=org,
            user=user,
        )
        if self._teamspace is None:
            raise ValueError("You need to pass a teamspace or an org for your deployment.")

        raise_access_error_if_not_allowed(AccessibleResource.Deployments, self._teamspace.id)

        self._deployment_api = DeploymentApi()
        self._cloud_account = _get_cluster(client=self._deployment_api._client, project_id=self._teamspace.id)
        self._is_created = False

        if name.startswith("dep_"):
            deployment = self._deployment_api.get_deployment_by_id(name, self._teamspace.id)
        else:
            deployment = self._deployment_api.get_deployment_by_name(name, self._teamspace.id)

        if deployment:
            self._name = deployment.name
            self._is_created = True
            self._deployment = deployment
        else:
            self._deployment = None

    def start(
        self,
        studio: Optional[Union[str, Studio]] = None,
        cloud: Optional[Union[CloudProvider, str]] = None,
        machine: Optional[Machine] = None,
        image: Optional[str] = None,
        autoscale: Optional[AutoScaleConfig] = None,
        ports: Optional[Union[float, List[float]]] = None,
        release_strategy: Optional[ReleaseStrategy] = None,
        entrypoint: Optional[str] = None,
        command: Optional[str] = None,
        commands: Optional[List[str]] = None,
        env: Union[List[Union[Secret, Env]], Dict[str, str], None] = None,
        spot: Optional[bool] = None,
        replicas: Optional[int] = None,
        health_check: Optional[Union[HttpHealthCheck, ExecHealthCheck]] = None,
        auth: Optional[Union[BasicAuth, TokenAuth, ApiKeyAuth]] = None,
        cloud_account: Optional[str] = None,
        custom_domain: Optional[str] = None,
        cloudspace_id: Optional[str] = None,
        quantity: Optional[int] = None,
        include_credentials: Optional[bool] = None,
        from_onboarding: Optional[bool] = None,
        from_litserve: Optional[bool] = None,
        max_runtime: Optional[int] = None,
        path_mappings: Optional[Dict[str, str]] = None,
        cloud_provider: Optional[CloudProvider] = None,
        model: Optional[str] = None,
        hf_token_secret: Optional[str] = None,
        base_image_variant: Optional[str] = None,
        tensor_parallel_size: Optional[int] = None,
        max_model_len: Optional[int] = None,
        gpu_memory_utilization: Optional[float] = None,
        quantization: Optional[str] = None,
        dtype: Optional[str] = None,
        extra_vllm_args: Optional[List[str]] = None,
        acknowledged_warnings: Optional[List[str]] = None,
    ) -> None:
        """The Lightning AI Deployment.

        This method creates the first release of the deployment.
        If a release already exists, it would raise a RuntimeError.

        Args:
            name: The name of the deployment.
            cloud: Cloud provider or cloud account to run replicas on.
            machine: The machine used by the deployment replicas.
            autoscale: The list of the metrics to autoscale on.
            ports: The ports to reach your replica services.
            image: The environement used by the deployment. Currentely, only docker images.
            release_strategy: The release strategy to use when changing core deployment specs.
            entrypoint: The docker container entrypoint.
            command: The docker container command.
            env: The environements variables or secrets to use.
            spot: Wether to use spot instances for the replicas.
            replicas: The number of replicas to deploy with.
            health_check: The health check config to know whether your service is ready to receive traffic.
            auth: The auth config to protect your services. Only Basic and Token supported.
            cloud_account: Deprecated. Use ``cloud`` instead. The name of the cloud account to run replicas on.
                Doesn't matter when the studio already exists.
            cloud_provider: Deprecated. Use ``cloud`` instead. The provider to select the cloud-account from.
            custom_domain: Whether your service would be referenced under a custom domain.
            cloudspace_id: Connect deployment to a Studio.
            quantity: The number of machines per replica to deploy.
            include_credentials: Whether to include the environment variables for the SDK to authenticate
            from_onboarding: Whether the deployment is from onboarding.
            max_runtime: the duration (in seconds) for which to allocate the machine.
                Irrelevant for most machines, required for some of the top-end machines on GCP.
                If in doubt, set it. Won't have an effect on machines not requiring it.
                Defaults to 3h
            path_mappings: Maps container paths to data-connection paths in the form
                ``{"<CONTAINER_PATH>": "<CONNECTION_NAME>:<PATH>"}`` or ``{"<CONTAINER_PATH>": "<CONNECTION_NAME>"}``
                for the root of a connection. Only applicable when deploying docker containers.

        Note:
            Since a teamspace can either be owned by an org or by a user directly,
            only one of the arguments can be provided.

        """
        raise_access_error_if_not_allowed(AccessibleResource.Deployments, self._teamspace.id)
        if self._is_created:
            raise RuntimeError("This deployment has already been started.")

        machine_image_version = None
        explicit_cloud_account = cloud_account
        explicit_cloud_provider = cloud_provider

        if isinstance(studio, Studio):
            cloudspace_id = studio._studio.id
            cloud_account = studio._studio.cluster_id
            machine_image_version = studio._studio.machine_image_version

        if isinstance(studio, str):
            studio = Studio(studio)
            cloudspace_id = studio._studio.id
            cloud_account = studio._studio.cluster_id
            machine_image_version = studio._studio.machine_image_version

        _warn_deprecated_cloud_selection(cloud_account=explicit_cloud_account, cloud_provider=explicit_cloud_provider)
        if cloud is not None and (explicit_cloud_account is not None or explicit_cloud_provider is not None):
            raise ValueError("Cannot use 'cloud' with 'cloud_account' or 'cloud_provider'.")
        if cloud_account is None:
            cloud_account = _resolve_default_cloud_account(cloud_account)

        if cloud_account is None and self._cloud_account is not None and cloud_provider is None:
            print(f"No cloud account was provided, defaulting to {self._cloud_account.cluster_id}")
            cloud_account = os.getenv("LIGHTNING_CLUSTER_ID") or self._cloud_account.cluster_id

        resolve_cloud = cloud if cloud_account is None else None
        _cloud_account = self._cloud_account_api.resolve_cloud_account(
            self.teamspace.id,
            cloud=resolve_cloud,
            cloud_account=cloud_account,
            cloud_provider=cloud_provider,
            default_cloud_account=self._teamspace.default_cloud_account,
        )

        if isinstance(ports, float):
            ports = [ports]

        if replicas is None and autoscale is None:
            replicas = 1

        if machine is None:
            machine = Machine.CPU

        if commands is not None and command is not None:
            raise ValueError("Commands and command are mutually exclusive")

        if commands is not None:
            command = compose_commands(commands)

        autoscaling_metric_name = ("CPU" if machine.is_cpu() else "GPU") if isinstance(machine, Machine) else "CPU"

        if autoscale is None:
            autoscale = AutoScaleConfig(
                min_replicas=0,
                max_replicas=1,
                metric=autoscaling_metric_name,
                threshold=90,
            )

        self._deployment = self._deployment_api.create_deployment(
            V1Deployment(
                autoscaling=to_autoscaling(autoscale, replicas),
                endpoint=to_endpoint(ports, auth, custom_domain),
                name=self._name,
                project_id=self._teamspace.id,
                replicas=replicas,
                cloudspace_id=cloudspace_id,
                spec=to_spec(
                    cloud_account=_cloud_account,
                    command=command,
                    entrypoint=entrypoint,
                    env=env,
                    image=image,
                    spot=spot,
                    machine=machine,
                    health_check=health_check,
                    quantity=quantity,
                    include_credentials=include_credentials if include_credentials is not None else True,
                    cloudspace_id=cloudspace_id,
                    max_runtime=max_runtime,
                    machine_image_version=machine_image_version,
                    path_mappings=path_mappings,
                    byom=model is not None,
                ),
                strategy=to_strategy(release_strategy),
                byom_spec=to_byom_spec(
                    model,
                    hf_token_secret=hf_token_secret,
                    base_image_variant=base_image_variant,
                    tensor_parallel_size=tensor_parallel_size,
                    max_model_len=max_model_len,
                    gpu_memory_utilization=gpu_memory_utilization,
                    quantization=quantization,
                    dtype=dtype,
                    extra_vllm_args=extra_vllm_args,
                ),
                acknowledged_warnings=acknowledged_warnings,
            ),
            from_onboarding=from_onboarding,
            from_litserve=from_litserve,
        )

        # Overrides the name
        self._name = self._deployment._name
        self._is_created = True

    def update(
        self,
        # Changing those arguments create a new release
        machine: Optional[Machine] = None,
        cloud: Optional[Union[CloudProvider, str]] = None,
        image: Optional[str] = None,
        entrypoint: Optional[str] = None,
        command: Optional[str] = None,
        commands: Optional[List[str]] = None,
        env: Optional[List[Union[Env, Secret]]] = None,
        spot: Optional[bool] = None,
        cloud_account: Optional[str] = None,
        health_check: Optional[Union[HttpHealthCheck, ExecHealthCheck]] = None,
        # Changing those arguments don't create a new release
        min_replicas: Optional[int] = None,
        max_replicas: Optional[int] = None,
        name: Optional[str] = None,
        ports: Optional[List[float]] = None,
        release_strategy: Optional[ReleaseStrategy] = None,
        replicas: Optional[int] = None,
        auth: Optional[Union[BasicAuth, TokenAuth]] = None,
        custom_domain: Optional[str] = None,
        quantity: Optional[int] = None,
        include_credentials: Optional[bool] = None,
        max_runtime: Optional[int] = None,
        path_mappings: Optional[Dict[str, str]] = None,
    ) -> None:
        """Update the deployment configuration.

        Changes to ``machine``, ``image``, ``entrypoint``, ``command``/``commands``, ``env``,
        ``spot``, ``cloud_account``, or ``health_check`` create a new release.  All other
        arguments (replica counts, ports, auth, etc.) are applied in-place without a new release.

        Args:
            machine: New machine type for the replicas.
            cloud: Cloud provider or cloud account to run replicas on.
            image: New docker image for the replicas.
            entrypoint: New container entrypoint.
            command: New container command string.
            commands: List of command strings, joined into a single command.  Mutually exclusive
                with ``command``.
            env: Environment variables or secrets to inject into replicas.
            spot: Whether to use spot/interruptible instances.
            cloud_account: Deprecated. Use ``cloud`` instead. Cloud account to run replicas on.
            health_check: Readiness probe configuration.
            min_replicas: New minimum replica count for autoscaling.
            max_replicas: New maximum replica count for autoscaling.
            name: New display name for the deployment.
            ports: Exposed port numbers.
            release_strategy: How to roll out the new release (e.g. blue/green).
            replicas: Fixed number of replicas (overrides autoscaling).
            auth: Authentication configuration for the deployment endpoint.
            custom_domain: Custom domain to attach to the deployment.
            quantity: Number of machines per replica.
            include_credentials: Whether to inject SDK authentication env vars.
            max_runtime: Maximum machine allocation duration in seconds.
            path_mappings: Container-path → data-connection-path mappings for docker jobs.
        """
        raise_access_error_if_not_allowed(AccessibleResource.Deployments, self._teamspace.id)
        _warn_deprecated_cloud_selection(cloud_account=cloud_account)
        if cloud is not None and cloud_account is not None:
            raise ValueError("Cannot use 'cloud' with 'cloud_account' or 'cloud_provider'.")
        cloud_account = _resolve_default_cloud_account(cloud_account)
        if cloud is not None:
            cloud_account = self._cloud_account_api.resolve_cloud_account(
                self.teamspace.id,
                cloud=cloud,
                cloud_account=cloud_account,
                cloud_provider=None,
                default_cloud_account=self._teamspace.default_cloud_account,
            )

        if command is None and commands is not None:
            command = compose_commands(commands)

        self._deployment = self._deployment_api.update_deployment(
            self._deployment,
            name=name or self._name,
            spot=spot,
            replicas=replicas,
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            cloud_account=cloud_account,
            machine=machine,
            image=image,
            entrypoint=entrypoint,
            command=command,
            ports=ports,
            custom_domain=custom_domain,
            auth=auth,
            env=env,
            health_check=health_check,
            release_strategy=release_strategy,
            quantity=quantity,
            include_credentials=include_credentials,
            max_runtime=max_runtime,
            path_mappings=path_mappings,
        )
        if self._deployment is not None:
            self._name = self._deployment.name

    def stop(self) -> None:
        """All the deployment replicas will be stopped and all their traffic blocked."""
        self._deployment = self._deployment_api.stop(self._deployment)

    def export_request_captures(
        self,
        *,
        start: DateTimeLike,
        end: DateTimeLike,
        output_dir: PathLike,
        paths: Optional[List[str]] = None,
        include_all_paths: bool = False,
        status_codes: Optional[List[int]] = None,
        strict: bool = False,
        request_timeout: Union[float, tuple] = 60,
        overwrite: bool = False,
        remote_path: Optional[str] = None,
    ) -> RequestCaptureExportResult:
        """Export captured request telemetry to local artifacts.

        The export is always written to ``output_dir``. If ``remote_path`` is provided,
        the same artifacts are also uploaded to that remote destination. This currently
        supports ``lightning_storage`` targets only.

        Args:
            start: Start of the time range to export captures for.
            end: End of the time range to export captures for.
            output_dir: Local directory where exported artifacts will be written.
            paths: Optional list of request paths to filter exports by.
            include_all_paths: If ``True``, export captures for all request paths.
            status_codes: Optional list of HTTP status codes to filter exports by.
            strict: If ``True``, raise an error on any export failure instead of skipping.
            request_timeout: Timeout in seconds (or ``(connect, read)`` tuple) for each request.
            overwrite: If ``True``, overwrite existing files in ``output_dir``.
            remote_path: Optional remote destination path for uploading exported artifacts.

        Returns:
            RequestCaptureExportResult: Summary of the export operation.

        Raises:
            RuntimeError: If the deployment has not been created yet.
        """
        if not self._deployment:
            raise RuntimeError("This deployment has not been created.")

        return self._deployment_api.export_request_captures(
            self._deployment,
            start=start,
            end=end,
            output_dir=output_dir,
            paths=paths,
            include_all_paths=include_all_paths,
            status_codes=status_codes,
            strict=strict,
            request_timeout=request_timeout,
            overwrite=overwrite,
            remote_path=remote_path,
        )

    @property
    def name(self) -> Optional[str]:
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            self._name = self._deployment.name
        return self._name

    @property
    def replicas(self) -> Optional[int]:
        """The default number of replicas the release starts with.

        Returns:
            Optional[int]: The replica count, or ``None`` if the deployment has not been started.
        """
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return self._deployment.replicas
        return None

    @property
    def min_replicas(self) -> Optional[int]:
        """The minimum number of replicas.

        Returns:
            Optional[int]: The autoscaling minimum replica count, or ``None`` if not started.
        """
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return int(self._deployment.autoscaling.min_replicas)
        return None

    @property
    def max_replicas(self) -> Optional[int]:
        """The maximum number of replicas.

        Returns:
            Optional[int]: The autoscaling maximum replica count, or ``None`` if not started.
        """
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return int(self._deployment.autoscaling.max_replicas)
        return None

    @property
    def ports(self) -> Optional[int]:
        """The exposed ports on which you can reach your deployment.

        Returns:
            Optional[int]: List of exposed port numbers, or ``None`` if not started.
        """
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return [int(p) for p in self._deployment.endpoint.ports]
        return None

    @property
    def release_strategy(self) -> Optional[ReleaseStrategy]:
        """The release strategy of the deployment.

        Returns:
            Optional[ReleaseStrategy]: The current release strategy, or ``None`` if not started.
        """
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return restore_release_strategy(self._deployment.strategy)
        return None

    @property
    def health_check(self) -> Optional[Union[HttpHealthCheck, ExecHealthCheck]]:
        """The health check to validate the replicas are ready to receive traffic.

        Returns:
            Optional[Union[HttpHealthCheck, ExecHealthCheck]]: The readiness probe configuration,
            or ``None`` if not started.
        """
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return restore_health_check(self._deployment.spec.readiness_probe)
        return None

    @property
    def auth(self) -> Optional[Auth]:
        """The authentification configuration of the deployment.

        Returns:
            Optional[Auth]: The authentication configuration, or ``None`` if not started.
        """
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return restore_auth(self._deployment.endpoint.auth)
        return None

    @property
    def autoscale(self) -> Optional[AutoScaleConfig]:
        """The autoscaling configuration of the deployment.

        Returns:
            Optional[AutoScaleConfig]: The autoscaling configuration, or ``None`` if not started.
        """
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return restore_autoscale(self._deployment.autoscaling)
        return None

    @property
    def env(self) -> Optional[List[Union[Secret, Env]]]:
        """The env configuration of the deployment.

        Returns:
            Optional[List[Union[Secret, Env]]]: The environment variables and secrets, or ``None`` if not started.
        """
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return restore_env(self._deployment.spec.env)
        return None

    @property
    def urls(self) -> Optional[List[str]]:
        """The urls to reach the deployment.

        Returns:
            Optional[List[str]]: The list of URLs for the deployment, or ``None`` if not started.
        """
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return self._deployment.status.urls
        return None

    @property
    def pending_replicas(self) -> Optional[int]:
        """The number of pending replicas.

        Returns:
            Optional[int]: The count of replicas currently pending, or ``None`` if not started.
        """
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return int(self._deployment.status.pending_replicas)
        return None

    @property
    def running_replicas(self) -> Optional[int]:
        """The number of failing replicas.

        Returns:
            Optional[int]: The count of replicas currently running and ready, or ``None`` if not started.
        """
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return int(self._deployment.status.ready_replicas)
        return None

    @property
    def failing_replicas(self) -> Optional[int]:
        """The number of failing replicas."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return int(self._deployment.status.failing_replicas)
        return None

    @property
    def deleting_replicas(self) -> Optional[int]:
        """The number of deleting replicas."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return int(self._deployment.status.deleting_replicas)
        return None

    @property
    def cloud_account(self) -> Optional[str]:
        """The cloud_account of the replicas."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return self._deployment.spec.cluster_id
        return None

    @property
    def release_id(self) -> Optional[str]:
        """The release id of the deployment."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return self._deployment.release_id
        return None

    @property
    def quantity(self) -> Optional[str]:
        """The number of machines per replica."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return self._deployment.spec.quantity
        return None

    @property
    def include_credentials(self) -> Optional[bool]:
        """The number of machines per replica."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return self._deployment.spec.include_credentials
        return None

    @property
    def org(self) -> Optional[Organization]:
        return self._org

    @property
    def user(self) -> Optional[User]:
        """The user of the deployment."""
        return self._user

    @property
    def teamspace(self) -> Optional[Teamspace]:
        """The teamspace of the deployment."""
        return self._teamspace

    @property
    def is_started(self) -> bool:
        return self._is_created

    @property
    def is_stopped(self) -> Optional[bool]:
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return self._deployment.autoscaling.max_replicas == 0
        return None

    @property
    def image(self) -> Optional[str]:
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return self._deployment.spec.image
        return None

    @property
    def entrypoint(self) -> Optional[str]:
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return self._deployment.spec.entrypoint
        return None

    @property
    def command(self) -> Optional[str]:
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return self._deployment.spec.command
        return None

    @property
    def _session(self) -> Any:
        if self._request_session is None:
            self._request_session = requests.Session()
            self._request_session.headers.update(**self._get_auth_headers())
        return self._request_session

    def _get_auth_headers(self) -> Dict:
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)

        if self._deployment.endpoint.auth.user_api_key:
            return {"Authorization": f"Bearer {self._auth.api_key}"}

        # TODO: Add support for all auth
        return {}

    def _get_url(self, port: Optional[int] = None) -> Any:
        urls = self.urls
        if urls is None:
            return None

        if port is None:
            return urls[0]

        return None

    def _prepare_url(self, path: str = "", port: Optional[int] = None) -> str:
        url = self._get_url(port)
        if url is None:
            raise ValueError("The url wasn't properly defined")

        if path.startswith("/"):
            path = path[1:]

        return f"{url}/{path}"

    def get(self, path: str = "", port: Optional[int] = None, **kwargs: Any) -> Any:
        return self._session.get(self._prepare_url(path, port), verify=False, **kwargs)

    def post(self, path: str = "", port: Optional[int] = None, **kwargs: Any) -> Any:
        return self._session.post(self._prepare_url(path, port), verify=False, **kwargs)

    def put(self, path: str = "", port: Optional[int] = None, **kwargs: Any) -> Any:
        return self._session.put(self._prepare_url(path, port), verify=False, **kwargs)

    def delete(self, path: str = "", port: Optional[int] = None, **kwargs: Any) -> Any:
        return self._session.delete(self._prepare_url(path, port), verify=False, **kwargs)
