"""Shared helpers for deployment CLI commands."""

import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

import click

from lightning_sdk.api.deployment_api import (
    ApiKeyAuth,
    AutoScaleConfig,
    BasicAuth,
    DeploymentApi,
    Env,
    RollingUpdateReleaseStrategy,
    Secret,
    TokenAuth,
)
from lightning_sdk.cli.job.run import _resolve_envs, _resolve_path_mapping
from lightning_sdk.cli.utils.save_to_config import save_teamspace_to_config
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.lightning_cloud.openapi import V1Deployment
from lightning_sdk.machine import Machine
from lightning_sdk.organization import Organization
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User
from lightning_sdk.utils.resolve import _get_authed_user

MACHINE_VALUES = tuple(
    [machine.name for machine in Machine.__dict__.values() if isinstance(machine, Machine) and machine._include_in_cli]
)


def resolve_teamspace(teamspace: Optional[str]) -> Teamspace:
    resolved_teamspace = TeamspacesMenu()(teamspace=teamspace)
    save_teamspace_to_config(resolved_teamspace, overwrite=False)
    return resolved_teamspace


def iter_teamspaces(teamspace: Optional[str], all_teamspaces: bool) -> Iterable[Teamspace]:
    if not all_teamspaces or teamspace:
        yield resolve_teamspace(teamspace)
        return

    user = _get_authed_user()
    menu = TeamspacesMenu()
    possible_teamspaces = menu._get_possible_teamspaces(user)
    for teamspace_name in possible_teamspaces.values():
        owner = menu._owner
        yield Teamspace(
            teamspace_name,
            org=owner if isinstance(owner, Organization) else None,
            user=owner if isinstance(owner, User) else None,
        )


def resolve_deployment(api: DeploymentApi, teamspace_id: str, name_or_id: str) -> V1Deployment:
    deployment = api.get_deployment_by_name(name_or_id, teamspace_id)
    if deployment is None:
        deployment = api.get_deployment_by_id(name_or_id, teamspace_id)
    if deployment is None:
        raise click.ClickException(f"Deployment {name_or_id!r} was not found.")
    return deployment


def resolve_machine(machine: Optional[str]) -> Optional[Machine]:
    if not machine:
        return None
    return Machine.from_str(machine)


def parse_ports(ports: Sequence[Union[int, float, str]]) -> Optional[List[Union[int, float]]]:
    if not ports:
        return None
    parsed_ports = []
    for port in ports:
        parsed = float(port)
        parsed_ports.append(int(parsed) if parsed.is_integer() else parsed)
    return parsed_ports


def parse_env(env: Sequence[str], secrets: Sequence[str]) -> Optional[List[Union[Env, Secret]]]:
    result: List[Union[Env, Secret]] = []
    for value in env:
        for key, env_value in _resolve_envs(value).items():
            result.append(Env(key, env_value))
    for secret in secrets:
        if secret:
            result.append(Secret(secret))
    return result or None


def parse_path_mappings(path_mapping: Sequence[str], path_mappings: str) -> Dict[str, str]:
    result = _resolve_path_mapping(path_mappings)
    for mapping in path_mapping:
        result.update(_resolve_path_mapping(mapping))
    return result


def parse_auth(
    api_key_auth: bool = False,
    basic_auth: Optional[str] = None,
    token_auth: Optional[str] = None,
) -> Optional[Union[ApiKeyAuth, BasicAuth, TokenAuth]]:
    selected = [bool(api_key_auth), basic_auth is not None, token_auth is not None]
    if sum(selected) > 1:
        raise click.UsageError("--api-key-auth, --basic-auth, and --token-auth are mutually exclusive.")

    if api_key_auth:
        return ApiKeyAuth()
    if token_auth is not None:
        return TokenAuth(token_auth)
    if basic_auth is not None:
        username, separator, password = basic_auth.partition(":")
        if not separator:
            raise click.UsageError("--basic-auth must be in USERNAME:PASSWORD format.")
        return BasicAuth(username=username, password=password)
    return None


def build_autoscale(
    machine: Optional[Machine],
    replicas: Optional[int],
    min_replicas: Optional[int],
    max_replicas: Optional[int],
    metric: Optional[str],
    threshold: Optional[float],
) -> Optional[AutoScaleConfig]:
    if replicas is None and min_replicas is None and max_replicas is None and metric is None and threshold is None:
        return None

    if replicas is not None:
        min_replicas = replicas if min_replicas is None else min_replicas
        max_replicas = replicas if max_replicas is None else max_replicas

    if metric is None:
        metric = "CPU" if machine is None or machine.is_cpu() else "GPU"
    if threshold is None:
        threshold = 90

    return AutoScaleConfig(
        min_replicas=min_replicas,
        max_replicas=max_replicas,
        metric=metric,
        threshold=threshold,
    )


def build_release_strategy(max_surge: int, max_unavailable: int) -> RollingUpdateReleaseStrategy:
    return RollingUpdateReleaseStrategy(max_surge=max_surge, max_unavailable=max_unavailable)


def deployment_to_dict(deployment: V1Deployment) -> Dict[str, Any]:
    return _json_safe(deployment.to_dict())


def to_json(data: Any) -> str:
    return json.dumps(_json_safe(data), indent=2, sort_keys=True)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value
