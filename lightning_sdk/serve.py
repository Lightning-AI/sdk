import os
import shlex
import subprocess
from pathlib import Path
from typing import Generator, Optional
from urllib.parse import urlencode

import docker
from rich.console import Console
from rich.progress import Progress

from lightning_sdk import Deployment, Machine, Teamspace
from lightning_sdk.api.deployment_api import AutoScaleConfig
from lightning_sdk.api.lit_container_api import LitContainerApi
from lightning_sdk.api.utils import _get_cloud_url
from lightning_sdk.lightning_cloud import env
from lightning_sdk.lightning_cloud.login import Auth, AuthServer

_DOCKER_NOT_RUNNING_MSG = (
    "Deploying LitServe requires Docker to be running on the machine. "
    "If Docker is not installed, please install it from https://docs.docker.com/get-docker/ "
    "and start the Docker daemon before running this command."
)


class _AuthServer(AuthServer):
    def get_auth_url(self, port: int) -> str:
        redirect_uri = f"http://localhost:{port}/login-complete"
        params = urlencode({"redirectTo": redirect_uri, "inviteCode": "litserve"})
        return f"{env.LIGHTNING_CLOUD_URL}/sign-in?{params}"


class _Auth(Auth):
    def _run_server(self) -> None:
        _AuthServer().login_with_browser(self)


class _LitServeDeployer:
    def __init__(self) -> None:
        self._console = Console()
        self._client = None

    @staticmethod
    def authenticate() -> None:
        auth = _Auth()
        auth.authenticate()

    @property
    def client(self) -> docker.DockerClient:
        if self._client is None:
            try:
                os.environ["DOCKER_BUILDKIT"] = "1"
                self._client = docker.from_env()
                self._client.ping()
            except docker.errors.DockerException:
                raise RuntimeError(_DOCKER_NOT_RUNNING_MSG) from None
        return self._client

    def dockerize_api(
        self,
        server_filename: str,
        port: int = 8000,
        gpu: bool = False,
        tag: str = "litserve-model",
        print_success: bool = True,
    ) -> str:
        import litserve as ls
        from litserve import docker_builder

        console = self._console
        requirements = ""
        if os.path.exists("requirements.txt"):
            requirements = "-r requirements.txt"
        else:
            console.print(
                f"requirements.txt not found at {os.getcwd()}. "
                f"Make sure to install the required packages in the Dockerfile.",
                style="yellow",
            )

        if os.path.exists("Dockerfile"):
            console.print(
                "Dockerfile already exists in the current directory, we will use it for building the container."
            )
            return os.path.abspath("Dockerfile")
        current_dir = Path.cwd()
        if not (current_dir / server_filename).is_file():
            raise FileNotFoundError(f"Server file `{server_filename}` must be in the current directory: {os.getcwd()}")

        version = ls.__version__
        if gpu:
            run_cmd = f"docker run --gpus all -p {port}:{port} {tag}:latest"
            docker_template = docker_builder.CUDA_DOCKER_TEMPLATE
        else:
            run_cmd = f"docker run -p {port}:{port} {tag}:latest"
            docker_template = docker_builder.DOCKERFILE_TEMPLATE
        dockerfile_content = docker_template.format(
            server_filename=server_filename,
            port=port,
            version=version,
            requirements=requirements,
        )
        with open("Dockerfile", "w") as f:
            f.write(dockerfile_content)

        if print_success:
            success_msg = f"""[bold]Dockerfile created successfully[/bold]
Update [underline]{os.path.abspath("Dockerfile")}[/underline] to add any additional dependencies or commands.

[bold]Build the container with:[/bold]
> [underline]docker build -t {tag} .[/underline]

[bold]To run the Docker container on the machine:[/bold]
> [underline]{run_cmd}[/underline]

[bold]To push the container to a registry:[/bold]
> [underline]docker push {tag}[/underline]
"""
            console.print(success_msg)
        return os.path.abspath("Dockerfile")

    @staticmethod
    def generate_client() -> None:
        from rich.console import Console

        console = Console()
        try:
            from litserve.python_client import client_template
        except ImportError:
            raise ImportError(
                "litserve is not installed. Please install it with `pip install lightning_sdk[serve]`"
            ) from None

        client_path = Path("client.py")
        if client_path.exists():
            console.print("Skipping client generation: client.py already exists", style="blue")
        else:
            try:
                client_path.write_text(client_template)
                console.print("✅ Client generated at client.py", style="bold green")
            except OSError as e:
                raise OSError(f"Failed to generate client.py: {e!s}") from None

    def _docker_build_with_logs(
        self, path: str, repository: str, tag: str, platform: str = "linux/amd64"
    ) -> Generator[str, None, None]:
        """Build Docker image using CLI with real-time log streaming.

        Returns:
            Tuple: (image_id, logs generator)

        Raises:
            RuntimeError: On build failure
        """
        cmd = f"docker build --platform {platform} -t {repository}:{tag} ."
        proc = subprocess.Popen(
            shlex.split(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line buffered
        )

        def log_generator() -> Generator[str, None, None]:
            while True:
                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                yield line.strip()
                if "error" in line.lower():
                    proc.terminate()
                    raise RuntimeError(f"Build failed: {line.strip()}")

            if proc.returncode != 0:
                raise RuntimeError(f"Build failed with exit code {proc.returncode}")

        return log_generator()

    def build_container(self, path: str, repository: str, tag: str, console: Console, progress: Progress) -> None:
        build_task = progress.add_task("Building Docker image", total=None)
        build_logs = self._docker_build_with_logs(path, repository, tag=tag)

        for line in build_logs:
            if "error" in line:
                progress.stop()
                console.print(f"\n[red]{line}[/red]")
                raise RuntimeError(f"Failed to build image: {line}")
            else:
                console.print(
                    line.strip(),
                )
                progress.update(build_task, description="Building Docker image")

        progress.update(build_task, description="[green]Build completed![/green]")

    def push_container(
        self, repository: str, tag: str, teamspace: Teamspace, lit_cr: LitContainerApi, progress: Progress
    ) -> dict:
        console = self._console
        push_task = progress.add_task("Pushing to registry", total=None)
        console.print("\nPushing image...", style="bold blue")
        lit_cr.authenticate()
        push_status = lit_cr.upload_container(repository, teamspace, tag=tag)
        last_status = {}
        for line in push_status:
            last_status = line
            if "error" in line:
                progress.stop()
                console.print(f"\n[red]{line}[/red]")
                raise RuntimeError(f"Failed to push image: {line}")
            if "status" in line:
                console.print(line["status"].strip())
                progress.update(push_task, description="Pushing to registry")
        progress.update(push_task, description="[green]Push completed![/green]")
        return last_status

    def _run_on_cloud(
        self,
        deployment_name: str,
        teamspace: Teamspace,
        image: str,
        metric: Optional[str] = None,
        machine: Optional[Machine] = None,
        min_replica: Optional[int] = 0,
        max_replica: Optional[int] = 1,
        spot: Optional[bool] = None,
        replicas: Optional[int] = 1,
        cloud_account: Optional[str] = None,
        port: Optional[int] = 8000,
        include_credentials: Optional[bool] = True,
    ) -> dict:
        url = f"{_get_cloud_url()}/{teamspace.owner.name}/{teamspace.name}/jobs/{deployment_name}"
        machine = machine or Machine.CPU
        metric = metric or ("CPU" if machine.is_cpu() else "GPU")
        deployment = Deployment(deployment_name, teamspace)
        if deployment.is_started:
            raise RuntimeError(
                f"Deployment with name {deployment_name} already running. "
                "Please stop the deployment before starting a new one.\n"
                f"You can access the deployment at {url}"
            )
        autoscale = AutoScaleConfig(min_replicas=min_replica, max_replicas=max_replica, metric=metric, threshold=0.95)
        deployment.start(
            machine=machine,
            image=image,
            autoscale=autoscale,
            spot=spot,
            replicas=replicas,
            cloud_account=cloud_account,
            ports=[port],
            include_credentials=include_credentials,
        )

        return {"deployment": deployment, "url": url}
