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
from lightning_sdk.api.job_api import JobApiV2
from lightning_sdk.api.mmt_api import MMTApiV2
from lightning_sdk.lightning_cloud.openapi.models import (
    V1CreateDeploymentRequest,
    V1PipelineStep,
    V1PipelineStepType,
    V1SharedFilesystem,
)
from lightning_sdk.machine import Machine
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
        cloud: Optional[Union["CloudProvider", str]] = None,
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
        custom_domain: Optional[str] = None,
        quantity: Optional[int] = None,
        include_credentials: Optional[bool] = None,
        max_runtime: Optional[int] = None,
        wait_for: Optional[Union[str, List[str]]] = DEFAULT,
    ) -> None:
        """Configure a deployment step in a pipeline.

        Args:
            name: Name of the deployment step.
            studio: Studio environment to use. Mutually exclusive with image.
            machine: Machine type to run on. Defaults to CPU.
            image: Docker image to run. Mutually exclusive with studio.
            autoscale: Auto-scaling configuration. Defaults to single-replica CPU/GPU scaling.
            ports: Ports to expose from the deployment.
            release_strategy: Strategy for releasing new versions of the deployment.
            entrypoint: Container entrypoint override.
            command: Command to run in the container.
            commands: List of commands to run in the container.
            env: Environment variables or secrets to inject.
            spot: Whether to use spot/interruptible instances.
            replicas: Number of initial replicas. Defaults to 1.
            health_check: Health check configuration for the deployment.
            auth: Authentication configuration for the deployment endpoint.
            cloud: Cloud provider or cloud account to run the deployment on.
            custom_domain: Custom domain for the deployment endpoint.
            quantity: Number of GPUs per replica (for multi-GPU setups).
            include_credentials: Whether to pass user credentials to the deployment.
            max_runtime: Maximum runtime in seconds.
            wait_for: Names of steps that must complete before this step starts.

        """
        self.name = name
        self.studio = _get_studio(studio)

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
        self.cloud = cloud
        self.custom_domain = custom_domain
        self.quantity = quantity
        self.include_credentials = include_credentials or True
        self.max_runtime = max_runtime
        self.wait_for = wait_for

    def to_proto(
        self, teamspace: "Teamspace", cloud_account: str, shared_filesystem: Union[bool, V1SharedFilesystem]
    ) -> V1PipelineStep:
        machine_image_version = None

        resolved_cloud_account = None
        if self.cloud is not None:
            resolved_cloud_account = CloudAccountApi().resolve_cloud_account(
                teamspace.id,
                default_cloud_account=teamspace.default_cloud_account,
                cloud=self.cloud,
            )

        studio = _get_studio(self.studio)
        if isinstance(studio, Studio):
            machine_image_version = studio._studio.machine_image_version

            if resolved_cloud_account is None:
                resolved_cloud_account = studio.cloud_account
            elif studio.cloud_account != resolved_cloud_account:
                raise ValueError("The provided cloud account doesn't match the studio")

        if resolved_cloud_account is None:
            resolved_cloud_account = CloudAccountApi().resolve_cloud_account(
                teamspace.id,
                default_cloud_account=teamspace.default_cloud_account,
                cloud=None,
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
                    cloud_account=resolved_cloud_account or cloud_account,
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
        cloud: Optional[Union["CloudProvider", str]] = None,
        name: Optional[str] = None,
        command: Optional[str] = None,
        studio: Union["Studio", str, None] = None,
        image: Union[str, None] = None,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
        image_credentials: Optional[str] = None,
        cloud_account_auth: bool = False,
        entrypoint: str = "sh -c",
        path_mappings: Optional[Dict[str, str]] = None,
        max_runtime: Optional[int] = None,
        wait_for: Union[str, List[str], None] = DEFAULT,
        reuse_snapshot: bool = True,
        scratch_disks: Optional[Dict[str, int]] = None,
        placement_group_id: Optional[str] = None,
    ) -> None:
        """Configure a job step in a pipeline.

        Args:
            machine: Machine type to run on. Defaults to CPU.
            name: Name of the job step.
            command: Command to run inside the job. Required if using a studio.
            studio: Studio environment to use. Mutually exclusive with image.
            image: Docker image to run. Mutually exclusive with studio.
            teamspace: Teamspace the job belongs to.
            org: Organization owning the teamspace.
            user: User owning the teamspace.
            cloud: Cloud provider or cloud account to run the job on.
            env: Environment variables to inject into the job.
            interruptible: Whether to use interruptible instances. Defaults to False.
            image_credentials: Name of the secret with credentials for pulling a private image.
            cloud_account_auth: Whether to use cloud account credentials to pull the image.
            entrypoint: Container entrypoint. Defaults to ``sh -c``.
            path_mappings: Mappings from container paths to data-connection paths.
            max_runtime: Maximum runtime in seconds.
            wait_for: Names of steps that must complete before this step starts.
            reuse_snapshot: Whether to reuse a studio snapshot across jobs. Defaults to True.
            scratch_disks: Extra volumes to mount under ``/teamspace/scratch``.
            placement_group_id: Optional placement group identifier for colocating the job.

        """
        self.name = name
        self.machine = machine or Machine.CPU
        self.command = command
        self.studio = _get_studio(studio)

        self.image = image
        self.teamspace = teamspace
        self.org = org
        self.user = user
        self.cloud = cloud
        self.env = env
        self.interruptible = interruptible
        self.image_credentials = image_credentials
        self.cloud_account_auth = cloud_account_auth
        self.entrypoint = entrypoint
        self.path_mappings = path_mappings
        self.max_runtime = max_runtime
        self.wait_for = wait_for
        self.reuse_snapshot = reuse_snapshot
        self.scratch_disks = scratch_disks
        self.placement_group_id = placement_group_id

    def to_proto(
        self, teamspace: "Teamspace", cloud_account: str, shared_filesystem: Union[bool, V1SharedFilesystem]
    ) -> V1PipelineStep:
        machine_image_version = None

        resolved_cloud_account = None
        if self.cloud is not None:
            resolved_cloud_account = CloudAccountApi().resolve_cloud_account(
                teamspace.id,
                default_cloud_account=teamspace.default_cloud_account,
                cloud=self.cloud,
            )

        studio = _get_studio(self.studio)
        if isinstance(studio, Studio):
            machine_image_version = studio._studio.machine_image_version

            if resolved_cloud_account is None:
                resolved_cloud_account = studio.cloud_account
            elif studio.cloud_account != resolved_cloud_account:
                raise ValueError("The provided cloud account doesn't match the studio")

        if resolved_cloud_account is None:
            resolved_cloud_account = CloudAccountApi().resolve_cloud_account(
                teamspace.id,
                default_cloud_account=teamspace.default_cloud_account,
                cloud=None,
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
            max_runtime=self.max_runtime,
            machine_image_version=machine_image_version,
            reuse_snapshot=self.reuse_snapshot,
            scratch_disks=self.scratch_disks,
            placement_group_id=self.placement_group_id,
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
        cloud: Optional[Union["CloudProvider", str]] = None,
        num_machines: Optional[int] = 2,
        command: Optional[str] = None,
        studio: Union["Studio", str, None] = None,
        image: Optional[str] = None,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
        image_credentials: Optional[str] = None,
        cloud_account_auth: bool = False,
        entrypoint: str = "sh -c",
        path_mappings: Optional[Dict[str, str]] = None,
        max_runtime: Optional[int] = None,
        wait_for: Optional[Union[str, List[str]]] = DEFAULT,
        reuse_snapshot: bool = True,
        placement_group_id: Optional[str] = None,
    ) -> None:
        """Configure a multi-machine training step in a pipeline.

        Args:
            name: Name of the multi-machine training step.
            machine: Machine type to run on.
            num_machines: Number of machines to allocate. Defaults to 2.
            command: Command to run inside the job. Required if using a studio.
            studio: Studio environment to use. Mutually exclusive with image.
            image: Docker image to run. Mutually exclusive with studio.
            teamspace: Teamspace the job belongs to.
            org: Organization owning the teamspace.
            user: User owning the teamspace.
            cloud: Cloud provider or cloud account to run the job on.
            env: Environment variables to inject into the job.
            interruptible: Whether to use interruptible instances. Defaults to False.
            image_credentials: Name of the secret with credentials for pulling a private image.
            cloud_account_auth: Whether to use cloud account credentials to pull the image.
            entrypoint: Container entrypoint. Defaults to ``sh -c``.
            path_mappings: Mappings from container paths to data-connection paths.
            max_runtime: Maximum runtime in seconds.
            wait_for: Names of steps that must complete before this step starts.
            reuse_snapshot: Whether to reuse a studio snapshot across jobs. Defaults to True.
            placement_group_id: Optional placement group identifier for colocating the job.

        """
        self.machine = machine or Machine.CPU
        self.num_machines = num_machines
        self.name = name
        self.command = command
        self.studio = _get_studio(studio)
        self.image = image
        self.teamspace = teamspace
        self.org = org
        self.user = user
        self.cloud = cloud
        self.env = env
        self.interruptible = interruptible
        self.image_credentials = image_credentials
        self.cloud_account_auth = cloud_account_auth
        self.entrypoint = entrypoint
        self.path_mappings = path_mappings
        self.max_runtime = max_runtime
        self.wait_for = wait_for
        self.reuse_snapshot = reuse_snapshot
        self.placement_group_id = placement_group_id

    def to_proto(
        self, teamspace: "Teamspace", cloud_account: str, shared_filesystem: Union[bool, V1SharedFilesystem]
    ) -> V1PipelineStep:
        machine_image_version = None

        resolved_cloud_account = None
        if self.cloud is not None:
            resolved_cloud_account = CloudAccountApi().resolve_cloud_account(
                teamspace.id,
                default_cloud_account=teamspace.default_cloud_account,
                cloud=self.cloud,
            )

        studio = _get_studio(self.studio)
        if isinstance(studio, Studio):
            machine_image_version = studio._studio.machine_image_version

            if resolved_cloud_account is None:
                resolved_cloud_account = studio.cloud_account
            elif studio.cloud_account != resolved_cloud_account:
                raise ValueError("The provided cloud account doesn't match the studio")

        if resolved_cloud_account is None:
            resolved_cloud_account = CloudAccountApi().resolve_cloud_account(
                teamspace.id,
                default_cloud_account=teamspace.default_cloud_account,
                cloud=None,
            )

        _validate_cloud_account(cloud_account, resolved_cloud_account, shared_filesystem)

        body = MMTApiV2._create_mmt_body(
            name=self.name,
            num_machines=self.num_machines,
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
            max_runtime=self.max_runtime,
            machine_image_version=machine_image_version,
            reuse_snapshot=self.reuse_snapshot,
            placement_group_id=self.placement_group_id,
        )

        return V1PipelineStep(
            name=self.name,
            type=V1PipelineStepType.MMT,
            wait_for=_to_wait_for(self.wait_for),
            mmt=body,
        )


class DeploymentReleaseStep(DeploymentStep):
    def __init__(self, *args: Any, deployment_name: Optional[str] = None, **kwargs: Any) -> None:
        """Configure a deployment release step that updates an existing deployment.

        Args:
            *args: Positional arguments forwarded to :class:`DeploymentStep`.
            deployment_name: Name of the existing deployment to update. Required.
            **kwargs: Keyword arguments forwarded to :class:`DeploymentStep`.

        Raises:
            ValueError: If deployment_name is not provided.
        """
        if not deployment_name:
            raise ValueError("The deployment name is required")
        self._deployment_name = deployment_name
        super().__init__(*args, **kwargs)

    def to_proto(self, *args: Any, **kwargs: Any) -> V1PipelineStep:
        proto: V1PipelineStep = super().to_proto(*args, **kwargs)
        proto.deployment.name = self._deployment_name
        proto.deployment.pipeline_reuse_deployment_between_runs = True
        return proto


__all__ = ["DeploymentReleaseStep", "DeploymentStep", "JobStep", "MMTStep"]
