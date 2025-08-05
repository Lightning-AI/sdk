from time import sleep
from typing import Any, Dict, List, Literal, Optional, Union

from lightning_sdk.api.utils import _machine_to_compute_name
from lightning_sdk.lightning_cloud.openapi import (
    CreateDeploymentRequestDefinesASpecForTheJobThatAllowsForAutoscalingJobs,
    V1AutoscalingSpec,
    V1AutoscalingTargetMetric,
    V1Deployment,
    V1DeploymentStrategy,
    V1Endpoint,
    V1EndpointAuth,
    V1EnvVar,
    V1HealthCheckExec,
    V1HealthCheckHttpGet,
    V1JobHealthCheckConfig,
    V1JobSpec,
    V1RollingUpdateStrategy,
)
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.machine import Machine

_METRICS = ["GPU", "CPU", "RPM"]


class Env:
    """The Env describes an environnement variable."""

    def __init__(self, name: str, value: str) -> str:
        self.name = name
        self.value = value


class Secret:
    """The Secret describes a protected environnement variable."""

    def __init__(self, name: str) -> str:
        self.name = name


class Auth:
    """The base auth class."""


class BasicAuth(Auth):
    """The BasicAuth describes the basic auth mechanism where a username and password are required to authenticate."""

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password


class TokenAuth(Auth):
    """The TokenAuth describes the token auth mechanism where a token is required to authenticate."""

    def __init__(self, token: str) -> None:
        self.token = token


class ReleaseStrategy:
    """The base class for release strategy."""


class RollingUpdateReleaseStrategy(ReleaseStrategy):
    """The RollingUpdateReleaseStrategy describes the rolling update strategy.

    Args:
        max_surge: The max_surge argument controls the maximum number of additional replicas
            that can be created during a rolling update.
            It specifies the number above the desired replica count that can be temporarily created.
            During an update, Lightning creates new replicas to replace the old ones,
            and the max_surge argument ensures that the total number of pods does not exceed a certain limit.
        max_unavailable: The max_unavailable argument determines the maximum number of replicas that
            can be unavailable during a rolling update. It specifies the maximum number that can be simultaneously
            removed from service during the update progresses. By default, Lightning terminates one replica at a
            time while creating new replicas, ensuring that the desired replica count is maintained.

    """

    def __init__(self, max_surge: int = 1, max_unavailable: int = 0) -> None:
        self.max_surge = max_surge
        self.max_unavailable = max_unavailable


class HealthCheck:
    pass


class ExecHealthCheck(HealthCheck):
    """The ExecHealthCheck determines whether your service is ready using exec command in the container.

    Args:
        command: The command to be executed within your container to decide whether the service is ready.
        timeout_seconds: The total number of time to wait before declaring the service as unhealthy.
        initial_delay_seconds: The amount of time to wait before starting to execute the command.
        failure_threshold: The total number of retries to do befor declaring the service as unhealthy.
        interval_seconds: The amount of time between retries.

    """

    def __init__(
        self,
        command: str,
        initial_delay_seconds: int = 0,
        failure_threshold: int = 3600,
        interval_seconds: int = 1,
        timeout_seconds: int = 30,
    ) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds
        self.initial_delay_seconds = initial_delay_seconds
        self.failure_threshold = failure_threshold
        self.interval_seconds = interval_seconds


class HttpHealthCheck(HealthCheck):
    """The HttpHealthCheck determines whether your service is ready using http request.

    Args:
        path: The server path to hit to check whether the server is healthy
        port: The server port to hit to check whether the server is healthy
        timeout_seconds: The total number of time to wait before declaring the service as unhealthy.
        initial_delay_seconds: The amount of time to wait before starting to execute the command.
        failure_threshold: The total number of retries to do befor declaring the service as unhealthy.
        interval_seconds: The amount of time between retries.

    """

    def __init__(
        self,
        path: str,
        port: float,
        initial_delay_seconds: int = 0,
        failure_threshold: int = 3600,
        interval_seconds: int = 1,
        timeout_seconds: int = 30,
    ) -> None:
        self.path = path
        self.port = port
        self.initial_delay_seconds = initial_delay_seconds
        self.failure_threshold = failure_threshold
        self.interval_seconds = interval_seconds
        self.timeout_seconds = timeout_seconds


class AutoScalingMetric:
    """The AutoScalingMetric determines the metric used to decide whether we should autoscale.

    Args:
        name: The name of the metric used to decide whether we should autoscale.
        target: The metric threshold  to decide whether we should autoscale.

    """

    def __init__(
        self,
        name: Literal["GPU", "CPU", "RPM"],
        target: float,
    ) -> None:
        self.name = name
        self.target = target


class AutoScaleConfig:
    """The AutoScaleConfig determines how to autoscale your deployment.

    Args:
        min_replicas: The minimum number of replicas. When set to 0, the replicas will
            stop when there is no traffic left.
        max_replicas: The maximum number of replicas.
        metric: The metric used to decide whether we should autoscale.
        threshold: The metric threshold  to decide whether we should autoscale.
        target_metrics: Multiple target metrics to autoscale the deployment.
        idle_threshold_seconds: The amount of time to wait before stopping a replica
            after the latest seen request.

    """

    def __init__(
        self,
        min_replicas: Optional[int] = None,
        max_replicas: Optional[int] = None,
        metric: Optional[Literal["GPU", "CPU", "RPM"]] = None,
        threshold: Optional[float] = None,
        target_metrics: Optional[List[AutoScalingMetric]] = None,
        idle_threshold_seconds: Optional[str] = None,
        scale_down_cooldown_seconds: Optional[str] = None,
        scale_up_cooldown_seconds: Optional[str] = None,
    ) -> None:
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.metric = metric
        self.threshold = threshold
        self.target_metrics = target_metrics
        self.idle_threshold_seconds = idle_threshold_seconds
        self.scale_down_cooldown_seconds = scale_down_cooldown_seconds
        self.scale_up_cooldown_seconds = scale_up_cooldown_seconds


class DeploymentApi:
    """Internal API client for Deployment requests (mainly http requests)."""

    def __init__(self, wait_on_stop: int = 5) -> None:
        self._client = LightningClient(max_tries=7)
        self._wait_on_stop = wait_on_stop

    def get_deployment_by_name(self, name: str, teamspace_id: str) -> Optional[V1Deployment]:
        try:
            return self._client.jobs_service_get_deployment_by_name(project_id=teamspace_id, name=name)
        except ApiException as ex:
            if "Reason: Not Found" in str(ex):
                return None
            raise ex

    def get_deployment_by_id(self, deployment_id: str, teamspace_id: str) -> Optional[V1Deployment]:
        try:
            return self._client.jobs_service_get_deployment(project_id=teamspace_id, id=deployment_id)
        except ApiException as ex:
            if "Reason: Not Found" in str(ex):
                return None
            raise ex

    def create_deployment(
        self,
        deployment: V1Deployment,
        from_onboarding: Optional[bool] = None,
        from_litserve: Optional[bool] = None,
    ) -> V1Deployment:
        return self._client.jobs_service_create_deployment(
            project_id=deployment.project_id,
            body=CreateDeploymentRequestDefinesASpecForTheJobThatAllowsForAutoscalingJobs(
                cloudspace_id=deployment.cloudspace_id,
                autoscaling=deployment.autoscaling,
                cluster_id=deployment.spec.cluster_id,
                endpoint=deployment.endpoint,
                name=deployment.name,
                replicas=deployment.replicas,
                spec=deployment.spec,
                strategy=deployment.strategy,
                from_onboarding=from_onboarding,
                from_litserve=from_litserve,
            ),
        )

    def update_deployment(
        self,
        deployment: V1Deployment,
        machine: Optional[Machine] = None,
        image: Optional[str] = None,
        entrypoint: Optional[str] = None,
        command: Optional[str] = None,
        env: Optional[List[Union[Env, Secret]]] = None,
        spot: Optional[bool] = None,
        cloud_account: Optional[str] = None,
        min_replicas: Optional[int] = None,
        max_replicas: Optional[int] = None,
        name: Optional[str] = None,
        ports: Optional[List[float]] = None,
        release_strategy: Optional[ReleaseStrategy] = None,
        replicas: Optional[int] = None,
        health_check: Optional[Union[HttpHealthCheck, ExecHealthCheck]] = None,
        auth: Optional[Union[BasicAuth, TokenAuth]] = None,
        custom_domain: Optional[str] = None,
        quantity: Optional[int] = None,
        include_credentials: Optional[bool] = None,
        max_runtime: Optional[int] = None,
    ) -> V1Deployment:
        # Update the deployment in place

        apply_change(deployment, "name", name)
        apply_change(deployment, "replicas", replicas)
        apply_change(deployment, "strategy", to_strategy(release_strategy))

        apply_change(deployment.autoscaling, "min_replicas", min_replicas)
        apply_change(deployment.autoscaling, "max_replicas", max_replicas)
        apply_change(deployment.autoscaling, "max_replicas", max_replicas)

        # Any updates to the Job Spec triggers a new release
        if machine:
            apply_change(deployment.spec, "instance_name", _machine_to_compute_name(machine))
            apply_change(deployment.spec, "instance_type", _machine_to_compute_name(machine))

        requires_release = False
        requires_release |= apply_change(deployment.spec, "image", image)

        requires_release |= apply_change(deployment.spec, "entrypoint", entrypoint)
        requires_release |= apply_change(deployment.spec, "command", command)
        requires_release |= apply_change(deployment.spec, "env", to_env(env))
        requires_release |= apply_change(deployment.spec, "readiness_probe", to_health_check(health_check, False))
        requires_release |= apply_change(deployment.spec, "cluster_id", cloud_account)
        requires_release |= apply_change(deployment.spec, "spot", spot)
        requires_release |= apply_change(deployment.spec, "quantity", quantity)
        requires_release |= apply_change(deployment.spec, "include_credentials", include_credentials)
        requires_release |= apply_change(
            deployment.spec, "requested_run_duration_seconds", str(max_runtime) if max_runtime is not None else None
        )

        if requires_release:
            if deployment.strategy is None:
                raise RuntimeError("When doing a new release, a release strategy needs to be defined.")

            print("Some core arguments have changed. We are making a new release.")

        apply_change(deployment.endpoint, "custom_domain", custom_domain)
        apply_change(deployment.endpoint, "auth", to_endpoint_auth(auth))
        apply_change(deployment.endpoint, "ports", [str(port) for port in ports] if ports else None)

        return self._client.jobs_service_update_deployment(
            project_id=deployment.project_id,
            id=deployment.id,
            body=deployment,
        )

    def stop(self, deployment: V1Deployment) -> V1Deployment:
        deployment.autoscaling.min_replicas = 0
        deployment.autoscaling.max_replicas = 0

        deployment = self._client.jobs_service_update_deployment(
            project_id=deployment.project_id,
            id=deployment.id,
            body=deployment,
        )

        # wait for all the replicas to be 0
        while deployment.replicas != 0:
            sleep(self._wait_on_stop)
            deployment = self.get_deployment_by_name(deployment.name, deployment.project_id)

        return deployment


def restore_release_strategy(strategy: V1DeploymentStrategy) -> Optional[ReleaseStrategy]:
    if not strategy:
        return None

    if strategy.rolling_update:
        return RollingUpdateReleaseStrategy(
            max_surge=strategy.rolling_update.max_surge,
            max_unavailable=strategy.rolling_update.max_unavailable,
        )
    raise ValueError("Only rolling update is supported for deployment. Stay tuned for more.")


def restore_health_check(readiness_probe: V1JobHealthCheckConfig) -> Optional[Union[HttpHealthCheck, ExecHealthCheck]]:
    if not readiness_probe:
        return None

    if readiness_probe.exec:
        return ExecHealthCheck(
            command=readiness_probe.exec.comand,
            failure_threshold=readiness_probe.failure_threshold,
            initial_delay_seconds=readiness_probe.initial_delay_seconds,
            interval_seconds=readiness_probe.interval_seconds,
            timeout_seconds=readiness_probe.timeout_seconds,
        )

    if readiness_probe.http_get:
        return HttpHealthCheck(
            path=readiness_probe.http_get.path,
            port=readiness_probe.http_get.port,
            failure_threshold=readiness_probe.failure_threshold,
            initial_delay_seconds=readiness_probe.initial_delay_seconds,
            interval_seconds=readiness_probe.interval_seconds,
            timeout_seconds=readiness_probe.timeout_seconds,
        )
    return None


def restore_auth(auth: Optional[V1EndpointAuth] = None) -> Optional[Auth]:
    if not auth:
        return None

    if auth.username and auth.password:
        return BasicAuth(username=auth.username, password=auth.password)

    if auth.token:
        return TokenAuth(token=auth.token)
    return None


def restore_autoscale(autoscaling: V1AutoscalingSpec) -> AutoScaleConfig:
    return [
        AutoScaleConfig(
            min_replicas=autoscaling.min_replicas,
            max_replicas=autoscaling.max_replicas,
            target_metrics=autoscaling.target_metric,
            idle_threshold_seconds=autoscaling.idle_threshold_seconds,
            scale_down_cooldown_seconds=autoscaling.scale_down_cooldown_seconds,
            scale_up_cooldown_seconds=autoscaling.scale_up_cooldown_seconds,
        )
    ]


def restore_env(env: List[V1EnvVar]) -> List[Union[Secret, Env]]:
    return [Secret(name=e.from_secret) if e.from_secret else Env(name=e.name, value=e.value) for e in env]


def to_env(env: Union[List[Union[Secret, Env]], Dict[str, str], None] = None) -> Optional[List[V1EnvVar]]:
    if not env:
        return None

    env_list = []

    if isinstance(env, dict):
        for k, v in env.items():
            env_list.append(Env(name=k, value=v))
    else:
        env_list = env

    return [
        V1EnvVar(name=env.name, value=env.value) if isinstance(env, Env) else V1EnvVar(from_secret=env.name)
        for env in env_list
    ]


def to_autoscaling(
    autoscale_config: Optional[AutoScaleConfig] = None, replicas: Optional[int] = None
) -> V1AutoscalingSpec:
    if not autoscale_config:
        raise ValueError("An autoscaling config should be provided.")

    min_replicas = autoscale_config.min_replicas
    max_replicas = autoscale_config.max_replicas
    metric = autoscale_config.metric
    threshold = autoscale_config.threshold
    target_metrics = autoscale_config.target_metrics

    if isinstance(replicas, int) and replicas < 0:
        raise ValueError("The number of replicas should be positive.")

    if isinstance(min_replicas, int) and min_replicas < 0:
        raise ValueError("The minimum number of replicas should be positive.")

    if isinstance(max_replicas, int) and max_replicas < 0:
        raise ValueError("The maximum number of replicas should be positive.")

    if min_replicas is None:
        if isinstance(replicas, int):
            print(f"The `min_replicas` wasn't provided. Defaulting to replicas: {replicas}.")
        else:
            print("The `min_replicas` wasn't provided. Defaulting to 0.")
            min_replicas = 0

    if max_replicas is None:
        if isinstance(replicas, int):
            print(f"The `max_replicas` wasn't provided. Defaulting to replicas: {replicas}.")
        else:
            print("The `max_replicas` wasn't provided. Defaulting to 1.")
            max_replicas = 1

    if min_replicas < 0:
        raise ValueError("The minimum number of replicas should be positive.")

    if min_replicas > max_replicas:
        raise ValueError("The minimum number of replicas should be smaller or equal to the maximum number of replicas.")

    if (metric is not None or threshold is not None) and target_metrics is not None:
        raise ValueError("Either metric and threshold, or target_metrics (for multiple) can be provided.")

    if target_metrics is None and (metric is None or (isinstance(metric, str) and metric not in _METRICS)):
        raise ValueError(f"The autoscaling metric is required. Currently supported metrics are {_METRICS}")

    if target_metrics is None and threshold is None:
        raise ValueError("The autoscaling threshold should be defined between 0 and 100.")

    if target_metrics is None and (threshold < 0 or threshold > 100):
        raise ValueError("The autoscaling threshold should be defined between 0 and 100.")

    if target_metrics is not None and len(target_metrics) == 0 and metric is None:
        raise ValueError("The target_metrics must be provided.")

    if target_metrics is not None:
        for target_metric in target_metrics:
            if target_metric.name is None or target_metric.name not in _METRICS:
                raise ValueError(f"The autoscaling metric is required. Currently supported metrics are {_METRICS}")
            if target_metric.target is None or target_metric.target < 0 or target_metric.target > 100:
                raise ValueError("The autoscaling threshold should be defined between 0 and 100.")

            # convert to string after validation
            target_metric.target = str(target_metric.target)

    metrics = (
        [V1AutoscalingTargetMetric(name=t.name, target=t.target) for t in target_metrics]
        if target_metrics is not None
        else [V1AutoscalingTargetMetric(name=metric, target=str(threshold))]
    )

    return V1AutoscalingSpec(
        enabled=True,
        min_replicas=min_replicas,
        max_replicas=max_replicas,
        target_metric=metrics,
        idle_threshold_seconds=autoscale_config.idle_threshold_seconds,
        scale_down_cooldown_seconds=autoscale_config.scale_down_cooldown_seconds,
        scale_up_cooldown_seconds=autoscale_config.scale_up_cooldown_seconds,
    )


def to_endpoint_auth(auth: Optional[Auth] = None) -> Optional[V1EndpointAuth]:
    if isinstance(auth, BasicAuth):
        if auth.username == "":
            raise ValueError("The username should be defined.")

        if auth.password == "":
            raise ValueError("The password should be defined.")

        return V1EndpointAuth(enabled=True, username=auth.username, password=auth.password)

    if isinstance(auth, TokenAuth):
        if auth.token == "":
            raise ValueError("The token should be defined.")

        return V1EndpointAuth(enabled=True, token=auth.token)
    return None


def to_endpoint(
    ports: Optional[List[float]] = None, auth: Optional[Auth] = None, custom_domain: Optional[str] = None
) -> V1Endpoint:
    if not ports:
        raise ValueError("At least one port is required to reach your deployment.")

    return V1Endpoint(
        auth=to_endpoint_auth(auth),
        custom_domain=custom_domain,
        ports=[str(port) for port in ports],
    )


def to_health_check(
    health_check: Optional[Union[HttpHealthCheck, ExecHealthCheck]] = None,
    use_default: bool = True,
) -> Optional[V1JobHealthCheckConfig]:
    if health_check is None and not use_default:
        return None

    # Use Default health check if none is provided
    if not health_check:
        return V1JobHealthCheckConfig(
            failure_threshold=3600,
            initial_delay_seconds=0,
            interval_seconds=1,
            timeout_seconds=60,
        )

    health_check_config = V1JobHealthCheckConfig(
        failure_threshold=health_check.failure_threshold,
        initial_delay_seconds=health_check.initial_delay_seconds,
        interval_seconds=health_check.interval_seconds,
        timeout_seconds=health_check.timeout_seconds,
    )

    if isinstance(health_check, HttpHealthCheck):
        health_check_config.http_get = V1HealthCheckHttpGet(
            path=health_check.path,
            port=health_check.port,
        )
    else:
        health_check_config._exec = V1HealthCheckExec(command=health_check.command)
    return health_check_config


def to_spec(
    cloud_account: Optional[str],
    machine: Optional[Machine],
    image: Optional[str],
    entrypoint: Optional[str],
    command: Optional[str],
    spot: Optional[bool] = False,
    env: Union[List[Union[Secret, Env]], Dict[str, str], None] = None,
    health_check: Optional[Union[HttpHealthCheck, ExecHealthCheck]] = None,
    quantity: Optional[int] = None,
    include_credentials: Optional[bool] = None,
    cloudspace_id: Optional[None] = None,
    max_runtime: Optional[int] = None,
    machine_image_version: Optional[str] = None,
) -> V1JobSpec:
    if cloud_account is None:
        raise ValueError("The cloud account should be defined.")

    if machine is None:
        raise ValueError("The machine should be defined.")

    if image is None and cloudspace_id is None:
        raise ValueError("The image should be defined.")

    if entrypoint is not None and cloudspace_id is not None:
        raise ValueError("The entrypoint shouldn't be defined when a Studio is provided.")

    if command is None and cloudspace_id is not None:
        raise ValueError("The command should be defined.")

    # need to go via kwargs for typing compatibility since autogenerated apis accept None but aren't typed with None
    optional_spec_kwargs = {}
    if max_runtime:
        optional_spec_kwargs["requested_run_duration_seconds"] = str(max_runtime)

    return V1JobSpec(
        cluster_id=cloud_account,
        command=command,
        entrypoint=entrypoint,
        env=to_env(env),
        image=image,
        spot=spot,
        instance_name=_machine_to_compute_name(machine),
        readiness_probe=to_health_check(health_check),
        quantity=quantity,
        include_credentials=include_credentials,
        cloudspace_id=cloudspace_id,
        machine_image_version=machine_image_version,
        **optional_spec_kwargs,
    )


def to_strategy(strategy: Optional[ReleaseStrategy]) -> None:
    if isinstance(strategy, RollingUpdateReleaseStrategy):
        return V1DeploymentStrategy(
            rolling_update=V1RollingUpdateStrategy(
                max_surge=strategy.max_surge,
                max_unavailable=strategy.max_unavailable,
            ),
            type="rolling_update",
        )
    return None


def apply_change(spec: Any, key: str, value: Any) -> bool:
    if value is None:
        return False

    if getattr(spec, key) != value:
        setattr(spec, key, value)
        return True

    return False


def compose_commands(commands: List[str]) -> str:
    composite_command = []

    for command in commands:
        command = command.strip()

        # Check if the command already has '&'
        if command.endswith("&"):
            # It's a background command, add it as a subshell without further adjustment
            composite_command.append(f"( {command} )")
        else:
            # Sequential execution, add as-is and use `&&` to connect if followed by another command
            composite_command.append(command)

    # Joining commands, using `&&` between sequential parts and respecting subshell backgrounds
    return " && ".join(composite_command)
