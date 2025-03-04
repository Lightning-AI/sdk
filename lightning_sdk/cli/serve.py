import subprocess
from pathlib import Path
from typing import Optional, Union

import click
import docker
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm

from lightning_sdk.api.lit_container_api import LitContainerApi
from lightning_sdk.cli.teamspace_menu import _TeamspacesMenu
from lightning_sdk.serve import _LitServeDeployer


@click.group("serve")
def serve() -> None:
    """Serve a LitServe model.

    Example:
        lightning serve api server.py  # serve locally

    Example:
        lightning serve api server.py --cloud  # deploy to the cloud

    You can deploy the API to the cloud by running `lightning serve api server.py --cloud`.
    This will generate a Dockerfile, build the image, and push it to the image registry.
    Deploying to the cloud requires pre-login to the docker registry.
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
@click.option("--gpu", is_flag=True, default=False, flag_value=True, help="Use GPU for serving")
@click.option("--repository", default=None, help="Docker repository name (e.g., 'username/model-name')")
@click.option(
    "--non-interactive",
    "--non_interactive",
    is_flag=True,
    default=False,
    flag_value=True,
    help="Do not prompt for confirmation",
)
def api(
    script_path: str,
    easy: bool,
    cloud: bool,
    gpu: bool,
    repository: str,
    non_interactive: bool,
) -> None:
    """Deploy a LitServe model script."""
    return api_impl(
        script_path=script_path, easy=easy, cloud=cloud, gpu=gpu, repository=repository, non_interactive=non_interactive
    )


def api_impl(
    script_path: Union[str, Path],
    easy: bool = False,
    cloud: bool = False,
    gpu: bool = False,
    repository: Optional[str] = None,
    non_interactive: bool = False,
) -> None:
    """Deploy a LitServe model script."""
    console = Console()
    script_path = Path(script_path)
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")
    if not script_path.is_file():
        raise ValueError(f"Path is not a file: {script_path}")

    ls_deployer = _LitServeDeployer()
    ls_deployer.generate_client() if easy else None

    if cloud:
        tag = repository if repository else "litserve-model"
        return _handle_cloud(script_path, console, gpu=gpu, tag=tag, non_interactive=non_interactive)

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
    gpu: bool,
    repository: str = "litserve-model",
    tag: Optional[str] = None,
    teamspace: Optional[str] = None,
    non_interactive: bool = False,
) -> None:
    try:
        client = docker.from_env()
        client.ping()
    except docker.errors.DockerException as e:
        raise RuntimeError(f"Failed to connect to Docker daemon: {e!s}. Is Docker running?") from None

    ls_deployer = _LitServeDeployer()
    path = ls_deployer.dockerize_api(script_path, port=8000, gpu=gpu, tag=tag)
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
    menu = _TeamspacesMenu()
    teamspace = menu._resolve_teamspace(teamspace)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        ls_deployer._build_container(path, repository, tag, console, progress)
        ls_deployer._push_container(repository, tag, teamspace, lit_cr, progress)
    console.print(f"\n✅ Image pushed to {tag}", style="bold green")
    console.print(
        "Soon you will be able to deploy this model to the Lightning Studio!",
    )
