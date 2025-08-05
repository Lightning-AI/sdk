from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from lightning_sdk.api.deployment_api import (
    AutoScaleConfig,
    AutoScalingMetric,
    BasicAuth,
    Env,
    ExecHealthCheck,
    HttpHealthCheck,
    ReleaseStrategy,
    Secret,
    TokenAuth,
    to_autoscaling,
    to_endpoint,
    to_spec,
    to_strategy,
)
from lightning_sdk.job.v2 import JobApiV2
from lightning_sdk.lightning_cloud.openapi.models import (
    V1CreateDeploymentRequest,
    V1PipelineStep,
    V1PipelineStepType,
    V1SharedFilesystem,
)
from lightning_sdk.machine import Machine
from lightning_sdk.mmt.v2 import MMTApiV2
from lightning_sdk.pipeline.utils import DEFAULT, _get_studio, _to_wait_for, _validate_cloud_account
from lightning_sdk.studio import CloudAccountApi, Studio

if TYPE_CHECKING:
    from lightning_sdk.organization import Organization
    from lightning_sdk.teamspace import CloudProvider, Teamspace
    from lightning_sdk.user import User


class DeploymentStep:
    # Note: This class is only temporary while pipeline is wip

    def __init__(
        self,
        name: Optional[str] = None,
        studio: Optional[Union[str, Studio]] = None,
        machine: Optional["Machine"] = None,
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
        auth: Optional[Union[BasicAuth, TokenAuth]] = None,
        cloud_account: Optional[str] = None,
        custom_domain: Optional[str] = None,
        quantity: Optional[int] = None,
        include_credentials: Optional[bool] = None,
        max_runtime: Optional[int] = None,
        wait_for: Optional[Union[str, List[str]]] = DEFAULT,
        cloud_provider: Optional[Union["CloudProvider", str]] = None,
    ) -> None:
        self.name = name
        self.studio = _get_studio(studio)
        if cloud_account and studio and cloud_account != studio.cloud_account != cloud_account:
            raise ValueError(
                f"The provided cloud account `{cloud_account}` doesn't match"
                f" the Studio cloud account {self.studio.cloud_account}"
            )

        self.machine = machine or Machine.CPU
        self.image = image
        autoscaling_metric_name = (
            ("CPU" if self.machine.is_cpu() else "GPU") if isinstance(self.machine, Machine) else "CPU"
        )
        self.autoscale = autoscale or AutoScaleConfig(
            min_replicas=0,
            max_replicas=1,
            target_metrics=[
                AutoScalingMetric(
                    name=autoscaling_metric_name,
                    target=80,
                )
            ],
        )
        self.ports = ports
        self.release_strategy = release_strategy
        self.entrypoint = entrypoint
        self.command = command
        self.commands = commands
        self.env = env
        self.spot = spot
        self.replicas = replicas or 1
        self.health_check = health_check
        self.auth = auth
        self.cloud_account = cloud_account or "" if self.studio is None else self.studio.cloud_account
        self.custom_domain = custom_domain
        self.quantity = quantity
        self.include_credentials = include_credentials or True
        self.max_runtime = max_runtime
        self.wait_for = wait_for
        self.cloud_provider = cloud_provider

    def to_proto(
        self, teamspace: "Teamspace", cloud_account: str, shared_filesystem: Union[bool, V1SharedFilesystem]
    ) -> V1PipelineStep:
        machine_image_version = None

        studio = _get_studio(self.studio)
        if isinstance(studio, Studio):
            machine_image_version = studio._studio.machine_image_version

            if self.cloud_account is None:
                self.cloud_account = studio.cloud_account
            elif studio.cloud_account != self.cloud_account:
                raise ValueError("The provided cloud account doesn't match the studio")

        resolved_cloud_account = CloudAccountApi().resolve_cloud_account(
            teamspace.id, self.cloud_account, self.cloud_provider, teamspace.default_cloud_account
        )

        _validate_cloud_account(cloud_account, resolved_cloud_account, shared_filesystem)

        return V1PipelineStep(
            name=self.name,
            type=V1PipelineStepType.DEPLOYMENT,
            wait_for=_to_wait_for(self.wait_for),
            deployment=V1CreateDeploymentRequest(
                autoscaling=to_autoscaling(self.autoscale, self.replicas),
                endpoint=to_endpoint(self.ports, self.auth, self.custom_domain),
                name=self.name,
                project_id=teamspace.id,
                replicas=self.replicas,
                spec=to_spec(
                    cloud_account=self.cloud_account or cloud_account,
                    command=self.command,
                    entrypoint=self.entrypoint,
                    env=self.env,
                    image=self.image,
                    spot=self.spot,
                    machine=self.machine,
                    health_check=self.health_check,
                    quantity=self.quantity,
                    cloudspace_id=self.studio._studio.id if self.studio else None,
                    include_credentials=self.include_credentials,
                    max_runtime=self.max_runtime,
                    machine_image_version=machine_image_version,
                ),
                strategy=to_strategy(self.release_strategy),
            ),
        )


class JobStep:
    # Note: This class is only temporary while pipeline is wip

    def __init__(
        self,
        machine: Optional[Union["Machine", str]] = None,
        name: Optional[str] = None,
        command: Optional[str] = None,
        studio: Union["Studio", str, None] = None,
        image: Union[str, None] = None,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        cloud_account: Optional[str] = None,
        cloud_provider: Optional[Union["CloudProvider", str]] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
        image_credentials: Optional[str] = None,
        cloud_account_auth: bool = False,
        entrypoint: str = "sh -c",
        path_mappings: Optional[Dict[str, str]] = None,
        max_runtime: Optional[int] = None,
        wait_for: Union[str, List[str], None] = DEFAULT,
    ) -> None:
        self.name = name
        self.machine = machine or Machine.CPU
        self.command = command
        self.studio = _get_studio(studio)

        if cloud_account and self.studio and cloud_account != self.studio.cloud_account != cloud_account:
            raise ValueError(
                f"The provided cloud account `{cloud_account}` doesn't match"
                f" the Studio cloud account {self.studio.cloud_account}"
            )

        self.image = image
        self.teamspace = teamspace
        self.org = org
        self.user = user
        self.cloud_account = cloud_account or "" if self.studio is None else self.studio.cloud_account
        self.cloud_provider = cloud_provider
        self.env = env
        self.interruptible = interruptible
        self.image_credentials = image_credentials
        self.cloud_account_auth = cloud_account_auth
        self.entrypoint = entrypoint
        self.path_mappings = path_mappings
        self.max_runtime = max_runtime
        self.wait_for = wait_for

    def to_proto(
        self, teamspace: "Teamspace", cloud_account: str, shared_filesystem: Union[bool, V1SharedFilesystem]
    ) -> V1PipelineStep:
        machine_image_version = None

        studio = _get_studio(self.studio)
        if isinstance(studio, Studio):
            machine_image_version = studio._studio.machine_image_version

            if self.cloud_account is None:
                self.cloud_account = studio.cloud_account
            elif studio.cloud_account != self.cloud_account:
                raise ValueError("The provided cloud account doesn't match the studio")

        resolved_cloud_account = CloudAccountApi().resolve_cloud_account(
            teamspace.id, self.cloud_account, self.cloud_provider, teamspace.default_cloud_account
        )

        _validate_cloud_account(cloud_account, resolved_cloud_account, shared_filesystem)

        body = JobApiV2._create_job_body(
            name=self.name,
            command=self.command,
            cloud_account=resolved_cloud_account or cloud_account,
            studio_id=studio._studio.id if isinstance(studio, Studio) else None,
            image=self.image,
            machine=self.machine,
            interruptible=self.interruptible,
            env=self.env,
            image_credentials=self.image_credentials,
            cloud_account_auth=self.cloud_account_auth,
            entrypoint=self.entrypoint,
            path_mappings=self.path_mappings,
            artifacts_local=None,
            artifacts_remote=None,
            max_runtime=self.max_runtime,
            machine_image_version=machine_image_version,
        )

        return V1PipelineStep(
            name=self.name,
            type=V1PipelineStepType.JOB,
            wait_for=_to_wait_for(self.wait_for),
            job=body,
        )


class MMTStep:
    # Note: This class is only temporary while pipeline is wip

    def __init__(
        self,
        name: str,
        machine: Union["Machine", str],
        num_machines: Optional[int] = 2,
        command: Optional[str] = None,
        studio: Union["Studio", str, None] = None,
        image: Optional[str] = None,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        cloud_account: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
        image_credentials: Optional[str] = None,
        cloud_account_auth: bool = False,
        entrypoint: str = "sh -c",
        path_mappings: Optional[Dict[str, str]] = None,
        max_runtime: Optional[int] = None,
        wait_for: Optional[Union[str, List[str]]] = DEFAULT,
    ) -> None:
        self.machine = machine or Machine.CPU
        self.num_machines = num_machines
        self.name = name
        self.command = command
        self.studio = _get_studio(studio)

        if cloud_account and self.studio and cloud_account != self.studio.cloud_account != cloud_account:
            raise ValueError(
                f"The provided cloud account `{cloud_account}` doesn't match"
                f" the Studio cloud account {self.studio.cloud_account}"
            )
        self.image = image
        self.teamspace = teamspace
        self.org = org
        self.user = user
        self.cloud_account = cloud_account or "" if self.studio is None else self.studio.cloud_account
        self.env = env
        self.interruptible = interruptible
        self.image_credentials = image_credentials
        self.cloud_account_auth = cloud_account_auth
        self.entrypoint = entrypoint
        self.path_mappings = path_mappings
        self.max_runtime = max_runtime
        self.wait_for = wait_for

    def to_proto(
        self, teamspace: "Teamspace", cloud_account: str, shared_filesystem: Union[bool, V1SharedFilesystem]
    ) -> V1PipelineStep:
        machine_image_version = None

        studio = _get_studio(self.studio)
        if isinstance(studio, Studio):
            machine_image_version = studio._studio.machine_image_version

            if self.cloud_account is None:
                self.cloud_account = studio.cloud_account
            elif studio.cloud_account != self.cloud_account:
                raise ValueError("The provided cloud account doesn't match the studio")

        _validate_cloud_account(cloud_account, self.cloud_account, shared_filesystem)

        body = MMTApiV2._create_mmt_body(
            name=self.name,
            num_machines=self.num_machines,
            command=self.command,
            cloud_account=self.cloud_account or cloud_account,
            studio_id=studio._studio.id if isinstance(studio, Studio) else None,
            image=self.image,
            machine=self.machine,
            interruptible=self.interruptible,
            env=self.env,
            image_credentials=self.image_credentials,
            cloud_account_auth=self.cloud_account_auth,
            entrypoint=self.entrypoint,
            path_mappings=self.path_mappings,
            artifacts_local=None,  # deprecated in favor of path_mappings
            artifacts_remote=None,  # deprecated in favor of path_mappings
            max_runtime=self.max_runtime,
            machine_image_version=machine_image_version,
        )

        return V1PipelineStep(
            name=self.name,
            type=V1PipelineStepType.MMT,
            wait_for=_to_wait_for(self.wait_for),
            mmt=body,
        )


class DeploymentReleaseStep(DeploymentStep):
    def __init__(self, *args: Any, deployment_name: Optional[str] = None, **kwargs: Any) -> None:
        if not deployment_name:
            raise ValueError("The deployment name is required")
        self._deployment_name = deployment_name
        super().__init__(*args, **kwargs)

    def to_proto(self, *args: Any, **kwargs: Any) -> V1PipelineStep:
        proto: V1PipelineStep = super().to_proto(*args, **kwargs)
        proto.deployment.name = self._deployment_name
        proto.deployment.pipeline_reuse_deployment_between_runs = True
        return proto


__all__ = ["JobStep", "MMTStep", "DeploymentStep", "DeploymentReleaseStep"]
