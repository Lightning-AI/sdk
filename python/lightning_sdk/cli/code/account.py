"""Org, plan and API key handling shared by the `lightning code` commands."""

import socket
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from typing import Optional

import rich_click as click

from lightning_sdk.api.api_key_api import ApiKeyApi
from lightning_sdk.api.utils import _get_cloud_url, cached_lightning_client
from lightning_sdk.lightning_cloud.openapi import V1APIKey, V1Organization

# The plan names GetBillingSubscription reports, by tier. A lapsed subscription reads as Free.
_TIERS = {"free": "free", "pro": "pro", "professional": "pro", "teams": "teams", "enterprise": "enterprise"}


@dataclass
class CodingOrg:
    """An org the user can bill coding tools to, with its plan."""

    id: str
    name: str
    display_name: str
    personal: bool
    coding_disabled: bool
    # None when the plan can't be read, e.g. a member without billing access
    plan: Optional[str]

    @property
    def tier(self) -> Optional[str]:
        if self.plan is None:
            return None
        return _TIERS.get(self.plan.lower(), "other")

    @property
    def label(self) -> str:
        title = self.display_name or self.name
        if self.personal:
            title = f"{title} (personal)"
        if title.lower() != self.name.lower() and not self.personal:
            title = f"{title} [{self.name}]"
        return title

    @property
    def plan_label(self) -> str:
        if self.coding_disabled:
            return "coding tools turned off"
        if self.plan is None:
            return "plan unknown"
        if self.tier == "free":
            return "Free, upgrade needed"
        return self.plan


def _plan_name(org_id: str) -> Optional[str]:
    try:
        return cached_lightning_client().billing_service_get_billing_subscription(org_id=org_id).name or "Free"
    except Exception:
        return None


def _coding_org(org: V1Organization, plan: Optional[str]) -> CodingOrg:
    return CodingOrg(
        id=org.id,
        name=org.name or "",
        display_name=org.display_name or "",
        personal=bool(org.is_personal_org),
        coding_disabled=bool(org.disable_coding_agents),
        plan=plan,
    )


def list_coding_orgs(*, with_plans: bool = True) -> list[CodingOrg]:
    """Return the user's orgs, the personal org first, with their plans unless ``with_plans`` is off."""
    orgs = cached_lightning_client().organizations_service_list_organizations().organizations or []
    coding_orgs = [_coding_org(org, None) for org in orgs]
    if with_plans:
        load_plans(coding_orgs)
    return sorted(coding_orgs, key=lambda org: (not org.personal, (org.display_name or org.name).lower()))


def load_plans(orgs: list[CodingOrg]) -> None:
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_plan_name, org.id) for org in orgs]
    for org, future in zip(orgs, futures):
        org.plan = future.result()


def _find_org(orgs: list[CodingOrg], name: str) -> CodingOrg:
    wanted = name.lower()
    for org in orgs:
        if wanted in (org.name.lower(), org.id.lower()):
            return org
    matches = [org for org in orgs if org.display_name.lower() == wanted]
    if len(matches) == 1:
        return matches[0]
    names = ", ".join(org.name for org in orgs)
    raise click.UsageError(f"You aren't a member of an organization named '{name}'. Yours: {names}")


def _interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def choose_org(org_name: Optional[str], *, previous_org_id: Optional[str] = None) -> CodingOrg:
    """Pick the org to bill: ``--org`` when given, otherwise ask, or use the only one there is."""
    orgs = list_coding_orgs(with_plans=False)
    if not orgs:
        raise click.ClickException("Your account isn't a member of any organization.")
    if org_name or len(orgs) == 1:
        org = _find_org(orgs, org_name) if org_name else orgs[0]
        load_plans([org])
        return org
    if not _interactive():
        names = ", ".join(org.name for org in orgs)
        raise click.UsageError(f"Choose the organization to bill with --org. Yours: {names}")

    load_plans(orgs)

    click.echo("Which organization should pay for code.lightning.ai?")
    width = len(str(len(orgs)))
    for number, org in enumerate(orgs, start=1):
        click.echo(f"  {number:>{width}}. {org.label}  ({org.plan_label})")
    default = next((i for i, org in enumerate(orgs, start=1) if org.id == previous_org_id), None)
    if default is None:
        default = next((i for i, org in enumerate(orgs, start=1) if org.tier not in (None, "free")), 1)
    number = click.prompt("Organization", type=click.IntRange(1, len(orgs)), default=default)
    return orgs[number - 1]


def upgrade_url(org: CodingOrg) -> str:
    return f"{_get_cloud_url()}/me/settings/coding-usage?coding_org={org.id}"


def require_coding_plan(org: CodingOrg) -> None:
    """Stop unless ``org``'s plan includes code.lightning.ai: Pro, Teams or Enterprise."""
    if org.coding_disabled:
        raise click.ClickException(
            f"Coding tools are turned off for {org.label}. Ask an org admin to turn them on, or pick another org."
        )
    if org.tier == "free":
        raise click.ClickException(
            f"{org.label} is on the Free plan, which doesn't include code.lightning.ai.\n"
            f"Upgrade to Pro or Teams to use it: {upgrade_url(org)}\n"
            f"Compare plans: {_get_cloud_url()}/pricing"
        )
    if org.tier is None:
        click.echo(f"Couldn't read the plan for {org.label}; continuing. Requests fail if it doesn't include coding.")


def default_key_name(tool: str) -> str:
    host = socket.gethostname().split(".")[0] or "unknown host"
    return f"{tool} on {host} {date.today().isoformat()}"


def create_key(org: CodingOrg, name: str, description: str) -> V1APIKey:
    """Create a Member-role key that bills ``org``, as the Coding Usage settings page does."""
    key = ApiKeyApi().create(org.id, name, description=description)
    if not key.raw_key:
        raise click.ClickException("The API key was created but its secret wasn't returned.")
    return key


def key_exists(org_id: str, key_id: str) -> bool:
    try:
        return any(key.id == key_id for key in ApiKeyApi().list(org_id))
    except Exception:
        return False


def revoke_key(org_id: str, key_id: str) -> bool:
    """Delete a key, returning whether it worked. A key someone already deleted counts as revoked."""
    try:
        ApiKeyApi().delete(org_id, key_id)
        return True
    except Exception:
        return not key_exists(org_id, key_id)
