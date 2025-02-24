from typing import TYPE_CHECKING, Dict, List, Optional, Union

from lightning_sdk.api.deployment_api import (
    AutoScaleConfig,
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
)

if TYPE_CHECKING:
    from lightning_sdk.machine import Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User


from lightning_sdk.pipeline.utils import DEFAULT


class Deployment:
    # Note: This class is only temporary while pipeline is wip

    def __init__(
        self,
        name: Optional[str] = None,
        machine: Optional["Machine"] = None,
        image: Optional[str] = None,
        autoscale: Optional["AutoScaleConfig"] = None,
        ports: Optional[List[float]] = None,
        release_strategy: Optional["ReleaseStrategy"] = None,
        entrypoint: Optional[str] = None,
        command: Optional[str] = None,
        env: Union[List[Union["Secret", "Env"]], Dict[str, str], None] = None,
        spot: Optional[bool] = None,
        replicas: Optional[int] = None,
        health_check: Optional[Union["HttpHealthCheck", "ExecHealthCheck"]] = None,
        auth: Optional[Union["BasicAuth", "TokenAuth"]] = None,
        cloud_account: Optional[str] = None,
        custom_domain: Optional[str] = None,
        quantity: Optional[int] = None,
        needs: Union[str, List[str]] = DEFAULT,
    ) -> None:
        self.name = name
        self.machine = machine
        self.image = image
        self.autoscale = autoscale
        self.ports = ports
        self.release_strategy = release_strategy
        self.entrypoint = entrypoint
        self.command = command
        self.env = env
        self.spot = spot
        self.replicas = replicas
        self.health_check = health_check
        self.auth = auth
        self.cloud_account = cloud_account
        self.custom_domain = custom_domain
        self.quantity = quantity
        self.needs = needs

    def to_proto(self, teamspace: "Teamspace") -> V1PipelineStep:
        return V1PipelineStep(
            name=self.name,
            type=V1PipelineStepType.DEPLOYMENT,
            needs=to_needs(self.needs),
            deployment=V1CreateDeploymentRequest(
                autoscaling=to_autoscaling(self.autoscale, self.replicas),
                endpoint=to_endpoint(self.ports, self.auth, self.custom_domain),
                name=self.name,
                project_id=teamspace.id,
                replicas=self.replicas,
                spec=to_spec(
                    cloud_account=self.cloud_account,
                    command=self.command,
                    entrypoint=self.entrypoint,
                    env=self.env,
                    image=self.image,
                    spot=self.spot,
                    machine=self.machine,
                    health_check=self.health_check,
                    quantity=self.quantity,
                ),
                strategy=to_strategy(self.release_strategy),
            ),
        )


class Job:
    # Note: This class is only temporary while pipeline is wip

    def __init__(
        self,
        machine: Union["Machine", str],
        name: Optional[str] = None,
        command: Optional[str] = None,
        studio: Union["Studio", str, None] = None,
        image: Union[str, None] = None,
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
        needs: Union[str, List[str]] = DEFAULT,
    ) -> None:
        self.name = name
        self.machine = machine
        self.command = command
        self.studio = studio
        self.image = image
        self.teamspace = teamspace
        self.org = org
        self.user = user
        self.cloud_account = cloud_account
        self.env = env
        self.interruptible = interruptible
        self.image_credentials = image_credentials
        self.cloud_account_auth = cloud_account_auth
        self.entrypoint = entrypoint
        self.path_mappings = path_mappings
        self.needs = needs

    def to_proto(self, teamspace: "Teamspace") -> V1PipelineStep:
        body = JobApiV2._create_job_body(
            name=self.name,
            command=self.command,
            cloud_account=self.cloud_account,
            studio_id=None,
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
        )

        return V1PipelineStep(
            name=self.name,
            type=V1PipelineStepType.JOB,
            needs=to_needs(self.needs),
            job=body,
        )


class MMT:
    # Note: This class is only temporary while pipeline is wip

    def __init__(
        self,
        machine: Union["Machine", str],
        num_machines: Optional[int] = 2,
        name: Optional[str] = None,
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
        needs: Union[str, List[str]] = DEFAULT,
    ) -> None:
        self.machine = machine
        self.num_machines = num_machines
        self.name = name
        self.command = command
        self.studio = studio
        self.image = image
        self.teamspace = teamspace
        self.org = org
        self.user = user
        self.cloud_account = cloud_account
        self.env = env
        self.interruptible = interruptible
        self.image_credentials = image_credentials
        self.cloud_account_auth = cloud_account_auth
        self.entrypoint = entrypoint
        self.path_mappings = path_mappings
        self.needs = needs


def to_needs(needs: Optional[Union[str, List[str]]]) -> Optional[List[str]]:
    if needs == DEFAULT:
        return needs

    if needs is None:
        return []

    return needs if isinstance(needs, list) else [needs]
