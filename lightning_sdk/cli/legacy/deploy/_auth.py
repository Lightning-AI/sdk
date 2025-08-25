import os
import time
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional, TypedDict
from urllib.parse import urlencode

from rich.console import Console
from rich.prompt import Confirm

from lightning_sdk import Teamspace
from lightning_sdk.api import UserApi
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.lightning_cloud import env
from lightning_sdk.lightning_cloud.login import Auth, AuthServer
from lightning_sdk.lightning_cloud.openapi import V1CloudSpace
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.utils.resolve import _get_authed_user, _resolve_teamspace

LITSERVE_CODE = os.environ.get("LITSERVE_CODE", "j39bzk903h")
_POLL_TIMEOUT = 120


class _AuthMode(Enum):
    DEVBOX = "dev"
    DEPLOY = "deploy"


class _AuthServer(AuthServer):
    def __init__(self, mode: _AuthMode, *args: Any, **kwargs: Any) -> None:
        self._mode = mode
        super().__init__(*args, **kwargs)

    def get_auth_url(self, port: int) -> str:
        redirect_uri = f"http://localhost:{port}/login-complete"
        params = urlencode({"redirectTo": redirect_uri, "mode": self._mode.value, "okbhrt": LITSERVE_CODE})
        return f"{env.LIGHTNING_CLOUD_URL}/sign-in?{params}"


class _AuthLitServe(Auth):
    def __init__(self, mode: _AuthMode, shall_confirm: bool = False) -> None:
        super().__init__()
        self._mode = mode
        self._shall_confirm = shall_confirm

    def _run_server(self) -> None:
        if self._shall_confirm:
            proceed = Confirm.ask(
                "[bold yellow]LitServe needs to authenticate with Lightning AI to deploy your server.[/bold yellow]\n"
                "This will open a browser window for login.\n"
                "Do you want to continue?",
                default=True,
            )
            if not proceed:
                raise RuntimeError(
                    "Login cancelled. Please login to Lightning AI to deploy the API. Run `lightning login` to login."
                )
        print("Opening browser for authentication...")
        print("Please come back to the terminal after logging in.")
        time.sleep(3)
        _AuthServer(self._mode).login_with_browser(self)


def authenticate(mode: _AuthMode, shall_confirm: bool = True) -> None:
    """Authenticate with Lightning AI.

    This will open a browser window for authentication.
    If `shall_confirm` is True, it will ask for confirmation before proceeding.
    """
    auth = _AuthLitServe(mode, shall_confirm)
    auth.authenticate()


def select_teamspace(teamspace: Optional[str], org: Optional[str], user: Optional[str]) -> Teamspace:
    if teamspace is None:
        user = _get_authed_user()
        menu = TeamspacesMenu()
        possible_teamspaces = menu._get_possible_teamspaces(user)
        if len(possible_teamspaces) == 1:
            name = next(iter(possible_teamspaces.values()))["name"]
            return Teamspace(name=name, org=org, user=user)

        return menu(teamspace)

    return _resolve_teamspace(teamspace=teamspace, org=org, user=user)


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
        self.client = LightningClient(max_tries=7)

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
        menu = TeamspacesMenu()
        self._wait_user_onboarding()
        # Onboarding has been completed - user already selected organization if they could
        possible_teamspaces = menu._get_possible_teamspaces(self.user)
        if len(possible_teamspaces) == 1:
            # User didn't select any org
            value = next(iter(possible_teamspaces.values()))
            return Teamspace(name=value["name"], org=value["org"], user=value["user"])

        for _, value in possible_teamspaces.items():
            # User select an org
            # Onboarding teamspace will be the default teamspace in the selected org
            if value["org"]:
                return Teamspace(name=value["name"], org=value["org"], user=value["user"])
        raise RuntimeError("Unable to select teamspace. Visit lightning.ai")
