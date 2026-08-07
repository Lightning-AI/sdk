import time
from datetime import datetime
from enum import Enum
from typing import List, Optional, TypedDict

import rich_click as click
from rich.console import Console

from lightning_sdk import Teamspace
from lightning_sdk.api import UserApi
from lightning_sdk.api.utils import cached_lightning_client
from lightning_sdk.cli.utils.resource_resolution import resolve_teamspace
from lightning_sdk.cli.utils.teamspace_option import resolve_teamspace as _resolve_teamspace_option
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi import V1CloudSpace
from lightning_sdk.utils.resolve import _get_authed_user

_POLL_TIMEOUT = 120


class _AuthMode(Enum):
    DEVBOX = "dev"
    DEPLOY = "deploy"


class _AuthLitServe(Auth):
    def __init__(self, mode: _AuthMode, shall_confirm: bool = False) -> None:
        super().__init__()
        self._mode = mode
        self._shall_confirm = shall_confirm

    def _run_server(self) -> None:
        raise click.UsageError("No Lightning credentials are available. Run `lightning login` first.")


def authenticate(mode: _AuthMode, shall_confirm: bool = True) -> None:
    """Validate existing Lightning AI credentials.

    Credentials must already be configured. Run ``lightning login`` first when
    credentials are unavailable.
    """
    auth = _AuthLitServe(mode, shall_confirm)
    auth.authenticate()


def select_teamspace(teamspace: Optional[str], org: Optional[str], user: Optional[str]) -> Teamspace:
    return _resolve_teamspace_option(teamspace=teamspace, org=org, user=user)


class _UserStatus(TypedDict):
    verified: bool
    onboarded: bool


def poll_verified_status(timeout: int = _POLL_TIMEOUT) -> _UserStatus:
    """Polls the verified status of the user until it is True or a timeout occurs."""
    user_api = UserApi()
    user = _get_authed_user()
    start_time = datetime.now()
    result = _UserStatus(onboarded=False, verified=False)
    while True:
        user_resp = user_api.get_user(name=user.name)
        result["onboarded"] = user_resp.status.completed_project_onboarding
        result["verified"] = user_resp.status.verified
        if user_resp.status.verified:
            return result
        if (datetime.now() - start_time).total_seconds() > timeout:
            break
        time.sleep(5)
    return result


class _OnboardingStatus(Enum):
    NOT_VERIFIED = "not_verified"
    ONBOARDING = "onboarding"
    ONBOARDED = "onboarded"


class _Onboarding:
    def __init__(self, console: Console) -> None:
        self.console = console
        self.user = _get_authed_user()
        self.user_api = UserApi()
        self.client = cached_lightning_client()

    @property
    def verified(self) -> bool:
        return self.user_api.get_user(name=self.user.name).status.verified

    @property
    def is_onboarded(self) -> bool:
        return self.user_api.get_user(name=self.user.name).status.completed_project_onboarding

    @property
    def can_join_org(self) -> bool:
        return len(self.client.organizations_service_list_joinable_organizations().joinable_organizations) > 0

    @property
    def status(self) -> _OnboardingStatus:
        if not self.verified:
            return _OnboardingStatus.NOT_VERIFIED
        if self.is_onboarded:
            return _OnboardingStatus.ONBOARDED
        return _OnboardingStatus.ONBOARDING

    def _wait_user_onboarding(self, timeout: int = _POLL_TIMEOUT) -> None:
        """Wait for user onboarding if they can join the teamspace otherwise move to select a teamspace."""
        status = self.status
        if status == _OnboardingStatus.ONBOARDED:
            return

        self.console.print("Waiting for account setup. Visit lightning.ai")
        start_time = datetime.now()
        while self.status != _OnboardingStatus.ONBOARDED:
            time.sleep(5)
            if self.is_onboarded:
                return
            if (datetime.now() - start_time).total_seconds() > timeout:
                break

        raise RuntimeError("Timed out waiting for onboarding status")

    def get_cloudspace_id(self, teamspace: Teamspace) -> Optional[str]:
        cloudspaces: List[V1CloudSpace] = self.client.cloud_space_service_list_cloud_spaces(teamspace.id).cloudspaces
        cloudspaces = sorted(cloudspaces, key=lambda cloudspace: cloudspace.created_at, reverse=True)
        if len(cloudspaces) == 0:
            raise RuntimeError("Error creating deployment! Finish account setup at lightning.ai first.")
        # get the first cloudspace
        cloudspace = cloudspaces[0]
        if "scratch-studio" in cloudspace.name or "scratch-studio" in cloudspace.display_name:
            return cloudspace.id
        return None

    def select_teamspace(self, teamspace: Optional[str], org: Optional[str], user: Optional[str]) -> Teamspace:
        """Select a teamspace while onboarding.

        If user is being onboarded and can't join any org, the teamspace it will be resolved to the default
         personal teamspace.
        If user is being onboarded and can join an org then it will select default teamspace from the org.
        """
        if self.is_onboarded:
            return select_teamspace(teamspace, org, user)

        # Run only when user hasn't completed onboarding yet.
        self._wait_user_onboarding()
        return resolve_teamspace(teamspace=teamspace, org=org, user=user)
