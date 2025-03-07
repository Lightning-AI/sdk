import os
import subprocess
from pathlib import Path
from typing import Optional, Union

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm

from lightning_sdk import Machine, Teamspace
from lightning_sdk.api.deployment_api import DeploymentApi
from lightning_sdk.api.lit_container_api import LitContainerApi
from lightning_sdk.cli.exceptions import StudioCliError
from lightning_sdk.cli.teamspace_menu import _TeamspacesMenu
from lightning_sdk.serve import _LitServeDeployer

_MACHINE_VALUES = tuple([machine.name for machine in Machine.__dict__.values() if isinstance(machine, Machine)])


@click.group("serve")
def serve() -> None:
    """Serve a LitServe model.

    Example:
        lightning serve api server.py  # serve locally

    Example:
        lightning serve api server.py --cloud --name litserve-api  # deploy to the cloud

    You can deploy the API to the cloud by running `lightning serve api server.py --cloud`.
    This will build a docker container for the server.py script and deploy it to the Lightning AI platform.
    """


@serve.command("api")
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
    help="Deploy the model to the Lightning AI platform",
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
    cloud: bool,
    name: str,
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
        cloud=cloud,
        repository=name,
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
        include_credentials=not no_credentials,
    )


def api_impl(
    script_path: Union[str, Path],
    easy: bool = False,
    cloud: bool = False,
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

    if cloud:
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
    if teamspace is None:
        menu = _TeamspacesMenu()
        resolved_teamspace = menu._resolve_teamspace(teamspace)
    else:
        resolved_teamspace = Teamspace(name=teamspace, org=org, user=user)

    port = port or 8000
    ls_deployer = _LitServeDeployer()
    path = ls_deployer.dockerize_api(script_path, port=port, gpu=not machine.is_cpu(), tag=tag, print_success=False)
    console.clear()
    if non_interactive:
        console.print("[italic]non-interactive[/italic] mode enabled, skipping confirmation prompts", style="blue")

    console.print(f"\nPlease review the Dockerfile at [u]{path}[/u] and make sure it is correct.", style="bold")
    correct_dockerfile = True if non_interactive else Confirm.ask("Is the Dockerfile correct?", default=True)
    if not correct_dockerfile:
        console.print("Please fix the Dockerfile and try again.", style="red")
        return

    tag = tag if tag else "latest"

    lit_cr = LitContainerApi()
    deployment_name = os.path.basename(repository)

    ls_deployer.authenticate()
    if DeploymentApi().get_deployment_by_name(deployment_name, resolved_teamspace.id):
        raise StudioCliError(f"Deployment {deployment_name} already exists. Please choose a different name.") from None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        try:
            ls_deployer.build_container(path, repository, tag, console, progress)
            push_status = ls_deployer.push_container(repository, tag, resolved_teamspace, lit_cr, progress)
        except Exception as e:
            console.print(f"❌ Deployment failed: {e}", style="red")
            return
    console.print(f"\n✅ Image pushed to {repository}:{tag}")
    console.print(f"🔗 You can access the container at: [i]{push_status.get('url')}[/i]")
    repository = push_status.get("repository")

    deployment_status = ls_deployer._run_on_cloud(
        deployment_name=deployment_name,
        image=repository,
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
    )
    console.print(f"🚀 Deployment started, access at [i]{deployment_status.get('url')}[/i]")
