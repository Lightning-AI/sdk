import os
import socket
import subprocess
import time
import webbrowser
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, TypedDict, Union
from urllib.parse import urlencode

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm

from lightning_sdk import Machine, Teamspace
from lightning_sdk.api import UserApi
from lightning_sdk.api.lit_container_api import LitContainerApi
from lightning_sdk.cli.teamspace_menu import _TeamspacesMenu
from lightning_sdk.lightning_cloud import env
from lightning_sdk.lightning_cloud.login import Auth, AuthServer
from lightning_sdk.lightning_cloud.openapi import V1CloudSpace
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.serve import _LitServeDeployer
from lightning_sdk.utils.resolve import _get_authed_user, _resolve_teamspace

_MACHINE_VALUES = tuple([machine.name for machine in Machine.__dict__.values() if isinstance(machine, Machine)])
_POLL_TIMEOUT = 600


class _ServeGroup(click.Group):
    def parse_args(self, ctx: click.Context, args: list) -> click.Group:
        # Check if first arg is a file path and not a command name
        if args and os.path.exists(args[0]) and args[0] not in self.commands:
            # Insert the 'api' command before the file path
            args.insert(0, "api")
        return super().parse_args(ctx, args)


@click.group("deploy", cls=_ServeGroup)
def deploy() -> None:
    """Deploy a LitServe model.

    Example:
        lightning deploy server.py  # deploy to the cloud

    Example:
        lightning deploy server.py --local  # run locally

    You can deploy the API to the cloud by running `lightning deploy server.py`.
    This will build a docker container for the server.py script and deploy it to the Lightning AI platform.
    """


@deploy.command("api")
@click.argument("script-path", type=click.Path(exists=True))
@click.option(
    "--easy",
    is_flag=True,
    default=False,
    flag_value=True,
    help="Generate a client for the model",
)
@click.option(
    "--local",
    is_flag=True,
    default=False,
    flag_value=True,
    help="Run the model locally",
)
@click.option("--name", default=None, help="Name of the deployed API (e.g., 'classification-api', 'Llama-api')")
@click.option(
    "--non-interactive",
    "--non_interactive",
    is_flag=True,
    default=False,
    flag_value=True,
    help="Do not prompt for confirmation",
)
@click.option(
    "--machine",
    default="CPU",
    show_default=True,
    type=click.Choice(_MACHINE_VALUES),
    help="The machine type to deploy the API on.",
)
@click.option(
    "--interruptible",
    is_flag=True,
    default=False,
    flag_value=True,
    help="Whether the machine should be interruptible (spot) or not.",
)
@click.option(
    "--teamspace",
    default=None,
    help="The teamspace the deployment should be associated with. Defaults to the current teamspace.",
)
@click.option(
    "--org",
    default=None,
    help="The organization owning the teamspace (if any). Defaults to the current organization.",
)
@click.option("--user", default=None, help="The user owning the teamspace (if any). Defaults to the current user.")
@click.option(
    "--cloud-account",
    "--cloud_account",
    default=None,
    help=(
        "The cloud account to run the deployment on. "
        "Defaults to the studio cloud account if running with studio compute env. "
        "If not provided will fall back to the teamspaces default cloud account."
    ),
)
@click.option("--port", default=8000, help="The port to expose the API on.")
@click.option("--min_replica", "--min-replica", default=0, help="Number of replicas to start with.")
@click.option("--max_replica", "--max-replica", default=1, help="Number of replicas to scale up to.")
@click.option("--replicas", "--replicas", default=1, help="Deployment will start with this many replicas.")
@click.option(
    "--no_credentials",
    "--no-credentials",
    is_flag=True,
    default=False,
    flag_value=True,
    help="Whether to include credentials in the deployment.",
)
def api(
    script_path: str,
    easy: bool,
    local: bool,
    name: Optional[str],
    non_interactive: bool,
    machine: str,
    interruptible: bool,
    teamspace: Optional[str],
    org: Optional[str],
    user: Optional[str],
    cloud_account: Optional[str],
    port: Optional[int],
    min_replica: Optional[int],
    max_replica: Optional[int],
    replicas: Optional[int],
    no_credentials: Optional[bool],
) -> None:
    """Deploy a LitServe model script."""
    return api_impl(
        script_path=script_path,
        easy=easy,
        local=local,
        repository=name,
        non_interactive=non_interactive,
        machine=machine,
        interruptible=interruptible,
        teamspace=teamspace,
        org=org,
        user=user,
        cloud_account=cloud_account,
        port=port,
        replicas=replicas,
        min_replica=min_replica,
        max_replica=max_replica,
        include_credentials=not no_credentials,
    )


def api_impl(
    script_path: Union[str, Path],
    easy: bool = False,
    local: bool = False,
    repository: [str] = None,
    tag: Optional[str] = None,
    non_interactive: bool = False,
    machine: str = "CPU",
    interruptible: bool = False,
    teamspace: Optional[str] = None,
    org: Optional[str] = None,
    user: Optional[str] = None,
    cloud_account: Optional[str] = None,
    port: Optional[int] = 8000,
    min_replica: Optional[int] = 0,
    max_replica: Optional[int] = 1,
    replicas: Optional[int] = 1,
    include_credentials: Optional[bool] = True,
) -> None:
    """Deploy a LitServe model script."""
    console = Console()
    script_path = Path(script_path)
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")
    if not script_path.is_file():
        raise ValueError(f"Path is not a file: {script_path}")

    _LitServeDeployer.generate_client() if easy else None

    if not repository:
        timestr = datetime.now().strftime("%b-%d-%H_%M")
        repository = f"litserve-{timestr}".lower()

    if not local:
        repository = repository or "litserve-model"
        machine = Machine.from_str(machine)
        return _handle_cloud(
            script_path,
            console,
            repository=repository,
            tag=tag,
            non_interactive=non_interactive,
            machine=machine,
            interruptible=interruptible,
            teamspace=teamspace,
            org=org,
            user=user,
            cloud_account=cloud_account,
            port=port,
            min_replica=min_replica,
            max_replica=max_replica,
            replicas=replicas,
            include_credentials=include_credentials,
        )

    try:
        subprocess.run(
            ["python", str(script_path)],
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        error_msg = f"Script execution failed with exit code {e.returncode}\nstdout: {e.stdout}\nstderr: {e.stderr}"
        raise RuntimeError(error_msg) from None


class _AuthServer(AuthServer):
    def get_auth_url(self, port: int) -> str:
        redirect_uri = f"http://localhost:{port}/login-complete"
        params = urlencode({"redirectTo": redirect_uri, "inviteCode": "litserve"})
        return f"{env.LIGHTNING_CLOUD_URL}/sign-in?{params}"


class _Auth(Auth):
    def __init__(self, shall_confirm: bool = False) -> None:
        super().__init__()
        self._shall_confirm = shall_confirm

    def _run_server(self) -> None:
        if self._shall_confirm:
            proceed = Confirm.ask(
                "Authenticating with Lightning AI. This will open a browser window. Continue?", default=True
            )
            if not proceed:
                raise RuntimeError(
                    "Login cancelled. Please login to Lightning AI to deploy the API."
                    " Run `lightning login` to login."
                ) from None
        print("Opening browser for authentication...")
        print("Please come back to the terminal after logging in.")
        time.sleep(3)
        _AuthServer().login_with_browser(self)


def authenticate(shall_confirm: bool = True) -> None:
    auth = _Auth(shall_confirm)
    auth.authenticate()


def select_teamspace(teamspace: Optional[str], org: Optional[str], user: Optional[str]) -> Teamspace:
    if teamspace is None:
        user = _get_authed_user()
        menu = _TeamspacesMenu()
        possible_teamspaces = menu._get_possible_teamspaces(user)
        if len(possible_teamspaces) == 1:
            name = next(iter(possible_teamspaces.values()))["name"]
            return Teamspace(name=name, org=org, user=user)

        return menu._resolve_teamspace(teamspace)

    return _resolve_teamspace(teamspace=teamspace, org=org, user=user)


class _UserStatus(TypedDict):
    verified: bool
    onboarded: bool


def poll_verified_status(timeout: int = _POLL_TIMEOUT) -> _UserStatus:
    """Polls the verified status of the user until it is True or a timeout occurs."""
    user_api = UserApi()
    user = _get_authed_user()
    start_time = datetime.now()
    result = {"onboarded": False, "verified": False}
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
        menu = _TeamspacesMenu()
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


def is_connected(host: str = "8.8.8.8", port: int = 53, timeout: int = 10) -> bool:
    try:
        socket.setdefaulttimeout(timeout)
        socket.create_connection((host, port))
        return True
    except OSError:
        return False


def _handle_cloud(
    script_path: Union[str, Path],
    console: Console,
    repository: str = "litserve-model",
    tag: Optional[str] = None,
    non_interactive: bool = False,
    machine: Machine = "CPU",
    interruptible: bool = False,
    teamspace: Optional[str] = None,
    org: Optional[str] = None,
    user: Optional[str] = None,
    cloud_account: Optional[str] = None,
    port: Optional[int] = 8000,
    min_replica: Optional[int] = 0,
    max_replica: Optional[int] = 1,
    replicas: Optional[int] = 1,
    include_credentials: Optional[bool] = True,
) -> None:
    if not is_connected():
        console.print("❌ Internet connection required to deploy to the cloud.", style="red")
        console.print("To run locally instead, use: `lightning serve [SCRIPT | server.py] --local`")
        return

    deployment_name = os.path.basename(repository)
    tag = tag if tag else "latest"

    if non_interactive:
        console.print("[italic]non-interactive[/italic] mode enabled, skipping confirmation prompts", style="blue")

    port = port or 8000
    ls_deployer = _LitServeDeployer(name=deployment_name, teamspace=None)
    path = ls_deployer.dockerize_api(script_path, port=port, gpu=not machine.is_cpu(), tag=tag, print_success=False)

    console.print(f"\nPlease review the Dockerfile at [u]{path}[/u] and make sure it is correct.", style="bold")
    correct_dockerfile = True if non_interactive else Confirm.ask("Is the Dockerfile correct?", default=True)
    if not correct_dockerfile:
        console.print("Please fix the Dockerfile and try again.", style="red")
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        try:
            # Build the container
            build_task = progress.add_task("Building Docker image", total=None)
            for line in ls_deployer.build_container(path, repository, tag):
                console.print(line.strip())
                progress.update(build_task, advance=1)
            progress.update(build_task, description="[green]Build completed![/green]", completed=1.0)
            progress.remove_task(build_task)

        except Exception as e:
            console.print(f"❌ Deployment failed: {e}", style="red")
            return

    # Push the container to the registry
    console.print("\nPushing container to registry. It may take a while...", style="bold")
    # Authenticate with LitServe affiliate
    authenticate(shall_confirm=not non_interactive)
    user_status = poll_verified_status()
    cloudspace_id: Optional[str] = None
    from_onboarding = False
    if not user_status["verified"]:
        console.print("❌ Verify phone number to continue. Visit lightning.ai.", style="red")
        return
    if not user_status["onboarded"]:
        console.print("onboarding user")
        onboarding = _Onboarding(console)
        resolved_teamspace = onboarding.select_teamspace(teamspace, org, user)
        cloudspace_id = onboarding.get_cloudspace_id(resolved_teamspace)
        from_onboarding = True
    else:
        resolved_teamspace = select_teamspace(teamspace, org, user)

    # list containers to create the project if it doesn't exist
    lit_cr = LitContainerApi()
    lit_cr.list_containers(resolved_teamspace.id, cloud_account=cloud_account)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        try:
            push_task = progress.add_task("Pushing to registry", total=None)
            push_status = {}
            for line in ls_deployer.push_container(
                repository, tag, resolved_teamspace, lit_cr, cloud_account=cloud_account
            ):
                push_status = line
                progress.update(push_task, advance=1)
                if not ("Pushing" in line["status"] or "Waiting" in line["status"]):
                    console.print(line["status"])
            progress.update(push_task, description="[green]Push completed![/green]")
        except Exception as e:
            console.print(f"❌ Deployment failed: {e}", style="red")
            return
    console.print(f"\n✅ Image pushed to {repository}:{tag}")
    image = push_status.get("image")

    deployment_status = ls_deployer.run_on_cloud(
        deployment_name=deployment_name,
        image=image,
        teamspace=resolved_teamspace,
        metric=None,
        machine=machine,
        spot=interruptible,
        cloud_account=cloud_account,
        port=port,
        min_replica=min_replica,
        max_replica=max_replica,
        replicas=replicas,
        include_credentials=include_credentials,
        cloudspace_id=cloudspace_id,
        from_onboarding=from_onboarding,
    )
    console.print(f"🚀 Deployment started, access at [i]{deployment_status.get('url')}[/i]")
    if user_status["onboarded"]:
        webbrowser.open(deployment_status.get("url"))
