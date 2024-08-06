import os
from typing import List, Optional, Union

from lightning_sdk.api.deployment_api import (
    Auth,
    AutoScaleConfig,
    BasicAuth,
    DeploymentApi,
    Env,
    ExecHealthCheck,
    HttpHealthCheck,
    ReleaseStrategy,
    Secret,
    TokenAuth,
    restore_auth,
    restore_autoscale,
    restore_env,
    restore_health_check,
    restore_release_strategy,
    to_autoscaling,
    to_endpoint,
    to_spec,
    to_strategy,
)
from lightning_sdk.lightning_cloud.openapi import V1Deployment
from lightning_sdk.machine import Machine
from lightning_sdk.organization import Organization
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User
from lightning_sdk.utils import _resolve_teamspace


class Deployment:
    """The Lightning AI Deployment.

    Allows to fully control a deployment, including retrieving the status, making new release
    and switching machine types, etc..

    Args:
        name: The name of the deployment.
        teamspace: The teamspace in which you want to deploy.
        org: The name of the organization owning the :param`teamspace` in case it is owned by an org
        user: The name of the user owning the :param`teamspace` in case it is owned directly by a user instead of an org

    Note:
        Since a teamspace can either be owned by an org or by a user directly,
        only one of the arguments can be provided.

    """

    def __init__(
        self,
        name: str,  # Only the name is required in case a deployment already exist.
        teamspace: Optional[Union[str, Teamspace]] = None,
        org: Optional[Union[str, Organization]] = None,
        user: Optional[Union[str, User]] = None,
    ) -> None:
        self._name = name
        self._org = org
        self._user = user
        self._deployment_api = DeploymentApi()
        self._teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
        self._is_created = False
        deployment = self._deployment_api.get_deployment_by_name(name, self._teamspace.id)
        if deployment:
            self._is_created = True
            self._deployment = deployment

    def start(
        self,
        machine: Optional[Machine] = None,
        environment: Optional[str] = None,
        autoscale: Optional[AutoScaleConfig] = None,
        ports: Optional[List[float]] = None,
        release_strategy: Optional[ReleaseStrategy] = None,
        entrypoint: Optional[str] = None,
        command: Optional[str] = None,
        env: Optional[List[Union[Env, Secret]]] = None,
        spot: Optional[bool] = None,
        replicas: Optional[int] = None,
        health_check: Optional[Union[HttpHealthCheck, ExecHealthCheck]] = None,
        auth: Optional[Union[BasicAuth, TokenAuth]] = None,
        cluster: Optional[str] = None,
        custom_domain: Optional[str] = None,
    ) -> None:
        """The Lightning AI Deployment.

        This method creates the first release of the deployment.
        If a release already exists, it would raise a RuntimeError.

        Args:
            name: The name of the deployment.
            machine: The machine used by the deployment replicas.
            autoscale: The list of the metrics to autoscale on.
            ports: The ports to reach your replica services.
            environment: The environement used by the deployment. Currentely, only docker images.
            release_strategy: The release strategy to use when changing core deployment specs.
            entrypoint: The docker container entrypoint.
            command: The docker container command.
            env: The environements variables or secrets to use.
            spot: Wether to use spot instances for the replicas.
            replicas: The number of replicas to deploy with.
            health_check: The health check config to know whether your service is ready to receive traffic.
            auth: The auth config to protect your services. Only Basic and Token supported.
            cluster: The name of the cluster, the studio should be created on.
                Doesn't matter when the studio already exists.
            custom_domain: Whether your service would be referenced under a custom doamin.

        Note:
            Since a teamspace can either be owned by an org or by a user directly,
            only one of the arguments can be provided.

        """
        if self._is_created:
            raise RuntimeError("This deployment has already been started.")

        self._deployment = self._deployment_api.create_deployment(
            V1Deployment(
                autoscaling=to_autoscaling(autoscale, replicas),
                endpoint=to_endpoint(ports, auth, custom_domain),
                name=self._name,
                project_id=self._teamspace.id,
                replicas=replicas,
                spec=to_spec(
                    cluster_id=cluster or os.getenv("LIGHTNING_CLUSTER_ID"),
                    command=command,
                    entrypoint=entrypoint,
                    env=env,
                    environment=environment,
                    spot=spot,
                    machine=machine,
                    health_check=health_check,
                ),
                strategy=to_strategy(release_strategy),
            )
        )
        self._is_created = True

    def update(
        self,
        # Changing those arguments create a new release
        machine: Optional[Machine] = None,
        environment: Optional[str] = None,
        entrypoint: Optional[str] = None,
        command: Optional[str] = None,
        env: Optional[List[Union[Env, Secret]]] = None,
        spot: Optional[bool] = None,
        cluster: Optional[str] = None,
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
    ) -> None:
        self._deployment = self._deployment_api.update_deployment(
            self._deployment,
            name=name or self._name,
            spot=spot,
            replicas=replicas,
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            cluster_id=cluster,
            machine=machine,
            environment=environment,
            entrypoint=entrypoint,
            command=command,
            ports=ports,
            custom_domain=custom_domain,
            auth=auth,
            env=env,
            health_check=health_check,
            release_strategy=release_strategy,
        )

    def stop(self) -> None:
        """All the deployment replicas will be stopped and all their traffic blocked."""
        self._deployment = self._deployment_api.stop(self._deployment)

    @property
    def replicas(self) -> Optional[int]:
        """The default number of replicas the release starts with."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return self._deployment.replicas
        return None

    @property
    def min_replicas(self) -> Optional[int]:
        """The minimum number of replicas."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return self._deployment.autoscaling.min_replicas
        return None

    @property
    def max_replicas(self) -> Optional[int]:
        """The maximum number of replicas."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return self._deployment.autoscaling.max_replicas
        return None

    @property
    def ports(self) -> Optional[int]:
        """The exposed ports on which you can reach your deployment."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return [int(p) for p in self._deployment.endpoint.ports]
        return None

    @property
    def release_strategy(self) -> Optional[ReleaseStrategy]:
        """The release strategy of the deployment."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return restore_release_strategy(self._deployment.strategy)
        return None

    @property
    def readiness_probe(self) -> Optional[Union[HttpHealthCheck, ExecHealthCheck]]:
        """The health check to validate the replicas are ready to receive traffic."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return restore_health_check(self._deployment.spec.readiness_probe)
        return None

    @property
    def auth(self) -> Optional[Auth]:
        """The authentification configuration of the deployment."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return restore_auth(self._deployment.endpoint.auth)
        return None

    @property
    def autoscale(self) -> Optional[AutoScaleConfig]:
        """The autoscaling configuration of the deployment."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return restore_autoscale(self._deployment.autoscaling)
        return None

    @property
    def env(self) -> Optional[AutoScaleConfig]:
        """The env configuration of the deployment."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return restore_env(self._deployment.spec.env)
        return None

    @property
    def urls(self) -> Optional[List[str]]:
        """The urls to reach the deployment."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return self._deployment.status.urls
        return None

    @property
    def pending_replicas(self) -> Optional[List[str]]:
        """The number of pending replicas."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return self._deployment.status.pending_replicas
        return None

    @property
    def failing_replicas(self) -> Optional[List[str]]:
        """The number of failing replicas."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return self._deployment.status.failing_replicas
        return None

    @property
    def deleting_replicas(self) -> Optional[List[str]]:
        """The number of deleting replicas."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return self._deployment.status.deleting_replicas
        return None

    @property
    def teamspace(self) -> Optional[Teamspace]:
        """The teamspace of the deployment."""
        return self._teamspace

    @property
    def is_started(self) -> bool:
        return self._is_created
