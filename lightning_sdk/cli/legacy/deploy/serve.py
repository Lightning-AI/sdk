import os
import socket
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from threading import Thread
from typing import Optional, Union

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm

from lightning_sdk import Machine, Teamspace
from lightning_sdk.api.lit_container_api import LitContainerApi
from lightning_sdk.api.utils import _get_registry_url
from lightning_sdk.cli.legacy.clusters_menu import _ClustersMenu
from lightning_sdk.cli.legacy.deploy._auth import (
    _AuthMode,
    _Onboarding,
    authenticate,
    poll_verified_status,
    select_teamspace,
)
from lightning_sdk.cli.legacy.deploy.devbox import _handle_devbox
from lightning_sdk.serve import _LitServeDeployer

_MACHINE_VALUES = tuple(
    [machine.name for machine in Machine.__dict__.values() if isinstance(machine, Machine) and machine._include_in_cli]
)


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
        lightning deploy server.py --cloud # deploy to the cloud

    Example:
        lightning deploy server.py  # run locally

    You can deploy the API to the cloud by running `lightning deploy server.py --cloud`.
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
    "--cloud",
    is_flag=True,
    default=False,
    flag_value=True,
    help="Run the model on cloud",
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
    help="Machine type to deploy the API on. Defaults to CPU.",
)
@click.option(
    "--devbox",
    default=None,
    show_default=True,
    type=click.Choice(_MACHINE_VALUES),
    help="Machine type to build the API on. Setting this argument will open the server in a Studio.",
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
@click.option("--replicas", default=1, help="Deployment will start with this many replicas.")
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
    cloud: bool,
    name: Optional[str],
    non_interactive: bool,
    machine: Optional[str],
    devbox: Optional[str],
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
        cloud=cloud,
        name=name,
        non_interactive=non_interactive,
        machine=machine,
        devbox=devbox,
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
    cloud: bool = False,
    name: Optional[str] = None,
    tag: Optional[str] = None,
    non_interactive: bool = False,
    machine: str = "CPU",
    devbox: Optional[str] = None,
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

    if not name:
        timestr = datetime.now().strftime("%b-%d-%H_%M")
        name = f"litserve-{timestr}".lower()

    if not cloud and not devbox:
        try:
            subprocess.run(
                ["python", str(script_path)],
                check=True,
                text=True,
            )
            return None
        except subprocess.CalledProcessError as e:
            error_msg = f"Script execution failed with exit code {e.returncode}\nstdout: {e.stdout}\nstderr: {e.stderr}"
            raise RuntimeError(error_msg) from None

    if devbox:
        machine = Machine.from_str(devbox)
        return _handle_devbox(name, script_path, console, non_interactive, machine, interruptible, teamspace, org, user)

    machine = Machine.from_str(machine)
    return _handle_cloud(
        script_path,
        console,
        repository=name,
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


def is_connected(host: str = "8.8.8.8", port: int = 53, timeout: int = 10) -> bool:
    try:
        socket.setdefaulttimeout(timeout)
        socket.create_connection((host, port))
        return True
    except OSError:
        return False


def _upload_container(
    console: Console,
    ls_deployer: _LitServeDeployer,
    repository: str,
    tag: str,
    resolved_teamspace: Teamspace,
    lit_cr: LitContainerApi,
    cloud_account: Optional[str],
) -> bool:
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        try:
            push_task = progress.add_task("Uploading container to Lightning registry", total=None)
            for line in ls_deployer.push_container(
                repository, tag, resolved_teamspace, lit_cr, cloud_account=cloud_account
            ):
                progress.update(push_task, advance=1)
                if not ("Pushing" in line["status"] or "Waiting" in line["status"]):
                    console.print(line["status"])
            progress.update(push_task, description="[green]Push completed![/green]")
        except Exception as e:
            console.print(f"❌ Deployment failed: {e}", style="red")
            return False
    console.print(f"\n✅ Image pushed to {repository}:{tag}")
    return True


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
        console.print("To run locally instead, use: `lightning serve [SCRIPT | server.py]`")
        return

    deployment_name = os.path.basename(repository)
    tag = tag if tag else "latest"

    if non_interactive:
        console.print("[italic]non-interactive[/italic] mode enabled, skipping confirmation prompts", style="blue")

    port = port or 8000
    ls_deployer = _LitServeDeployer(name=deployment_name, teamspace=None)
    path = ls_deployer.dockerize_api(script_path, port=port, gpu=not machine.is_cpu(), tag=tag, print_success=False)

    console.print(f"\n[bold]LitServe generated a Dockerfile at:[/bold]\n[u]{path}[/u]\n")
    console.print("Please check that it matches your server setup.")
    correct_dockerfile = (
        True
        if non_interactive
        else Confirm.ask("Have you reviewed the Dockerfile and confirmed it's correct?", default=True)
    )
    if not correct_dockerfile:
        console.print("[red]Dockerfile review canceled. Please update the Dockerfile and try again.[/red]")
        return

    console.print(
        "Building your container image now.\n[cyan bold]Make sure Docker is installed and running.[/cyan bold]\n"
    )
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
            console.print(
                "❌ Failed to build a container for your server.\n"
                "Make sure Docker is installed and running, then try again.",
                f"\n\nError details: {e}",
                style="red",
            )
            return

    # Push the container to the registry
    console.print("\nPushing container to registry. It may take a while...", style="bold")
    # Authenticate with LitServe affiliate
    authenticate(_AuthMode.DEPLOY, shall_confirm=not non_interactive)
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

    lightning_containers_cloud_account = cloud_account
    if not cloud_account:
        clusters_menu = _ClustersMenu()
        lightning_containers_cloud_account = clusters_menu._resolve_cluster(resolved_teamspace)
        cloud_account = resolved_teamspace.default_cloud_account

    # list containers to create the project if it doesn't exist
    lit_cr = LitContainerApi()
    lit_cr.list_containers(resolved_teamspace.id, cloud_account=lightning_containers_cloud_account)

    registry_url = _get_registry_url()
    container_basename = repository.split("/")[-1]
    image = (
        f"{registry_url}/lit-container"
        + (f"-{lightning_containers_cloud_account}" if lightning_containers_cloud_account is not None else "")
        + f"/{resolved_teamspace.owner.name}/{resolved_teamspace.name}/{container_basename}"
    )

    if from_onboarding:
        thread = Thread(
            target=ls_deployer.run_on_cloud,
            kwargs={
                "deployment_name": deployment_name,
                "image": image,
                "teamspace": resolved_teamspace,
                "metric": None,
                "machine": machine,
                "spot": interruptible,
                "cloud_account": cloud_account,
                "port": port,
                "min_replica": min_replica,
                "max_replica": max_replica,
                "replicas": replicas,
                "include_credentials": include_credentials,
                "cloudspace_id": cloudspace_id,
                "from_onboarding": from_onboarding,
            },
        )
        thread.start()
        console.print("🚀 Deployment started")
        if not _upload_container(
            console, ls_deployer, repository, tag, resolved_teamspace, lit_cr, lightning_containers_cloud_account
        ):
            thread.join()
            return
        thread.join()
        return

    if not _upload_container(
        console, ls_deployer, repository, tag, resolved_teamspace, lit_cr, lightning_containers_cloud_account
    ):
        return

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
