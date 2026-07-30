from typing import Optional, Union

import rich_click as click

from lightning_sdk.api.cloud_account_api import CloudAccountApi
from lightning_sdk.job import Job
from lightning_sdk.lightning_cloud.openapi import V1ClusterType
from lightning_sdk.mmt import MMT
from lightning_sdk.studio import Studio
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.utils.resolve import _resolve_teamspace


def join_teamspace_slug(owner: Optional[str], teamspace: Optional[str]) -> Optional[str]:
    if teamspace is None:
        return None
    return f"{owner}/{teamspace}" if owner else teamspace


def resolve_teamspace(
    teamspace: Optional[str] = None,
    org: Optional[str] = None,
    user: Optional[str] = None,
) -> Teamspace:
    if teamspace and "/" in teamspace and (org or user):
        raise click.UsageError("--teamspace already specifies its owner; remove --org/--user.")
    resolved = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
    if resolved is None:
        raise click.UsageError("Could not resolve a teamspace. Pass --teamspace OWNER/TEAMSPACE.")
    return resolved


def resolve_cluster(
    teamspace: Teamspace,
    cloud_account: Optional[str],
    option_name: str,
) -> Optional[str]:
    selected = cloud_account or teamspace.default_cloud_account
    if selected is None:
        raise click.UsageError(f"No default cloud account is configured. Pass {option_name} ACCOUNT.")

    resolved = CloudAccountApi().get_cloud_account_non_org(
        cloud_account_id=selected,
        teamspace_id=teamspace.id,
    )
    if resolved is None:
        raise click.UsageError(f"Could not resolve cloud account '{selected}'. Pass {option_name} ACCOUNT.")
    return None if resolved.spec.cluster_type == V1ClusterType.GLOBAL else resolved.id


def resolve_studio(name: Optional[str], teamspace: Teamspace) -> Studio:
    try:
        return Studio(name=name, teamspace=teamspace, create_ok=False)
    except ValueError as ex:
        detail = f" '{name}'" if name else ""
        raise click.UsageError(f"Could not resolve studio{detail}. Pass --name STUDIO.") from ex


def resolve_job(name: Optional[str], teamspace: Teamspace) -> Job:
    if not name:
        raise click.UsageError("Missing job name. Pass JOB.")
    try:
        return Job(name=name, teamspace=teamspace)
    except ValueError as ex:
        raise click.UsageError(f"Could not resolve job '{name}' in teamspace '{teamspace.name}'.") from ex


def resolve_job_or_mmt(name: Optional[str], teamspace: Teamspace) -> Union[Job, MMT]:
    """Resolve a single- or multi-machine job by name."""
    if not name:
        raise click.UsageError("Missing job name. Pass JOB.")

    try:
        return Job(name=name, teamspace=teamspace)
    except ValueError:
        pass

    try:
        return MMT(name=name, teamspace=teamspace)
    except ValueError as ex:
        raise click.UsageError(f"Could not resolve job '{name}' in teamspace '{teamspace.name}'.") from ex


def resolve_mmt_machine(mmt: MMT, rank: int) -> Job:
    """Resolve one machine in a multi-machine job by rank."""
    machines = mmt.machines
    if not machines:
        raise click.ClickException(f"Job '{mmt.name}' has no machines.")

    expected = f"{mmt.name}-{rank}"
    for machine in machines:
        if machine.name == expected:
            return machine

    prefix = f"{mmt.name}-"
    available_ranks = []
    for machine in machines:
        if machine.name.startswith(prefix):
            suffix = machine.name[len(prefix) :]
            if suffix.isdigit():
                available_ranks.append(int(suffix))
    available = ", ".join(str(value) for value in sorted(available_ranks))
    raise click.ClickException(f"Rank {rank} not found on job '{mmt.name}'. Available ranks: {available or 'none'}.")


def resolve_mmt(name: Optional[str], teamspace: Teamspace) -> MMT:
    if not name:
        raise click.UsageError("Missing multi-machine job name. Pass JOB.")
    try:
        return MMT(name=name, teamspace=teamspace)
    except ValueError as ex:
        raise click.UsageError(f"Could not resolve multi-machine job '{name}' in teamspace '{teamspace.name}'.") from ex
