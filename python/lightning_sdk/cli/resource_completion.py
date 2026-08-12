"""Non-interactive shell completion for Lightning resources."""

import os
from typing import Optional

import rich_click as click
from click.shell_completion import CompletionItem

from lightning_sdk.api.utils import cached_lightning_client
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.utils.config import Config, DefaultConfigKeys


def has_credentials() -> bool:
    """Check for existing credentials without starting the browser login flow."""
    auth = Auth()
    if auth.api_key or auth.auth_token:
        return True
    if not auth.load():
        return False
    return bool(auth.api_key or auth.auth_token)


def accessible_teamspaces() -> dict[str, dict[str, str]]:
    """Return accessible teamspace IDs grouped by owner name."""
    client = cached_lightning_client()
    user = client.auth_service_get_user()
    organizations = client.organizations_service_list_organizations().organizations
    memberships = client.projects_service_list_memberships(filter_by_user_id=True).memberships

    owner_names_by_id = {user.id: user.username}
    owner_names_by_id.update({organization.id: organization.name for organization in organizations})
    teamspaces: dict[str, dict[str, str]] = {owner_name: {} for owner_name in owner_names_by_id.values()}

    for membership in memberships:
        owner_name = owner_names_by_id.get(membership.owner_id)
        if owner_name is not None:
            teamspaces[owner_name][membership.name] = membership.project_id

    return teamspaces


def studios(teamspace_id: str) -> dict[str, str]:
    """Return every Studio visible in a teamspace, following API pagination."""
    client = cached_lightning_client()
    kwargs = {"project_id": teamspace_id}
    studio_ids: dict[str, str] = {}

    while True:
        response = client.cloud_space_service_list_cloud_spaces(**kwargs)
        studio_ids.update({studio.name: studio.id for studio in response.cloudspaces})
        if not response.next_page_token:
            return studio_ids
        kwargs["page_token"] = response.next_page_token


def complete_teamspace(
    _ctx: click.Context,
    _param: click.Parameter,
    incomplete: str,
) -> list[CompletionItem]:
    """Complete canonical ``owner/teamspace`` slugs."""
    try:
        if not has_credentials():
            return []
        values = []
        for owner, teamspaces in accessible_teamspaces().items():
            for teamspace in teamspaces:
                slug = f"{owner}/{teamspace}"
                if slug.startswith(incomplete) or teamspace.startswith(incomplete):
                    values.append(CompletionItem(slug))
        return sorted(values, key=lambda item: item.value)
    except Exception:
        return []


def complete_studio(
    ctx: click.Context,
    _param: click.Parameter,
    incomplete: str,
) -> list[CompletionItem]:
    """Complete Studios in the selected or configured teamspace."""
    try:
        if not has_credentials():
            return []
        teamspaces = accessible_teamspaces()
        teamspace = ctx.params.get("teamspace") or _configured_teamspace()
        teamspace_ids = _matching_teamspace_ids(teamspaces, teamspace)
        if not teamspace_ids:
            return []

        names: set[str] = set()
        for teamspace_id in teamspace_ids:
            names.update(studios(teamspace_id))
        return [CompletionItem(name) for name in sorted(names) if name.startswith(incomplete)]
    except Exception:
        return []


def _configured_teamspace() -> Optional[str]:
    configured = os.environ.get("LIGHTNING_TEAMSPACE")
    if configured:
        return configured

    config = Config()
    name = config.get_value(DefaultConfigKeys.teamspace_name)
    owner = config.get_value(DefaultConfigKeys.teamspace_owner)
    if name and owner and "/" not in name:
        return f"{owner}/{name}"
    return name


def _matching_teamspace_ids(teamspaces: dict[str, dict[str, str]], selected: Optional[str]) -> list[str]:
    if selected and "/" in selected:
        owner, teamspace = selected.split("/", 1)
        teamspace_id = teamspaces.get(owner, {}).get(teamspace)
        return [teamspace_id] if teamspace_id else []
    if selected:
        return [values[selected] for values in teamspaces.values() if selected in values]

    all_ids = [teamspace_id for values in teamspaces.values() for teamspace_id in values.values()]
    return all_ids if len(all_ids) == 1 else []
