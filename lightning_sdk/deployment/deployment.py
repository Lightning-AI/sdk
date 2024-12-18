import os
from typing import Any, Dict, List, Optional, Union

import requests

from lightning_sdk.api import UserApi
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
from lightning_sdk.lightning_cloud import login
from lightning_sdk.lightning_cloud.openapi import V1Deployment
from lightning_sdk.machine import Machine
from lightning_sdk.organization import Organization
from lightning_sdk.services.utilities import _get_cluster
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User
from lightning_sdk.utils.resolve import _resolve_deprecated_cluster, _resolve_org, _resolve_teamspace, _resolve_user


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
        self._request_session = None

        self._auth = login.Auth()

        try:
            self._auth.authenticate()
            if user is None:
                self._user = User(name=UserApi()._get_user_by_id(self._auth.user_id).username)
        except ConnectionError as e:
            raise e

        self._name = name
        self._org = _resolve_org(org)
        self._user = _resolve_user(user)
        self._teamspace = _resolve_teamspace(
            teamspace=teamspace, org=self._org, user=self._user if self._org is None else None
        )
        if self._teamspace is None:
            raise ValueError("You need to pass a teamspace or an org for your deployment.")

        self._deployment_api = DeploymentApi()
        self._cloud_account = _get_cluster(client=self._deployment_api._client, project_id=self._teamspace.id)
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
        cloud_account: Optional[str] = None,
        custom_domain: Optional[str] = None,
        cluster: Optional[str] = None,  # deprecated in favor of cloud_account
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
            cloud_account: The name of the cloud account, the studio should be created on.
                Doesn't matter when the studio already exists.
            custom_domain: Whether your service would be referenced under a custom doamin.

        Note:
            Since a teamspace can either be owned by an org or by a user directly,
            only one of the arguments can be provided.

        """
        if self._is_created:
            raise RuntimeError("This deployment has already been started.")

        cloud_account = _resolve_deprecated_cluster(cloud_account, cluster)

        if cloud_account is None and self._cloud_account is not None:
            print(f"No cloud account was provided, defaulting to {self._cloud_account.cluster_id}")
            cloud_account = os.getenv("LIGHTNING_CLUSTER_ID") or self._cloud_account.cluster_id

        self._deployment = self._deployment_api.create_deployment(
            V1Deployment(
                autoscaling=to_autoscaling(autoscale, replicas),
                endpoint=to_endpoint(ports, auth, custom_domain),
                name=self._name,
                project_id=self._teamspace.id,
                replicas=replicas,
                spec=to_spec(
                    cloud_account=cloud_account,
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
        cluster: Optional[str] = None,  # deprecated in favor of cloud_account
    ) -> None:
        cloud_account = _resolve_deprecated_cluster(cloud_account, cluster)

        self._deployment = self._deployment_api.update_deployment(
            self._deployment,
            name=name or self._name,
            spot=spot,
            replicas=replicas,
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            cloud_account=cloud_account,
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
    def cloud_account(self) -> Optional[str]:
        """The cloud_account of the replicas."""
        if self._deployment:
            self._deployment = self._deployment_api.get_deployment_by_name(self._name, self._teamspace.id)
            return self._deployment.spec.cluster_id
        return None

    @property
    def user(self) -> Optional[User]:
        """The teamspace of the deployment."""
        return self._user

    @property
    def teamspace(self) -> Optional[Teamspace]:
        """The teamspace of the deployment."""
        return self._teamspace

    @property
    def is_started(self) -> bool:
        return self._is_created

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
