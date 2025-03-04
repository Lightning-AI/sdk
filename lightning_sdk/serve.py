import os
import warnings
from pathlib import Path

import docker
from rich.console import Console
from rich.progress import Progress

from lightning_sdk import Teamspace
from lightning_sdk.api.lit_container_api import LitContainerApi


class _LitServeDeployer:
    def __init__(self) -> None:
        self._console = Console()
        self._client = None

    @property
    def client(self) -> docker.DockerClient:
        if self._client is None:
            try:
                self._client = docker.from_env()
                self._client.ping()
            except docker.errors.DockerException as e:
                raise RuntimeError(f"Failed to connect to Docker daemon: {e!s}. Is Docker running?") from None
        return self._client

    def dockerize_api(
        self, server_filename: str, port: int = 8000, gpu: bool = False, tag: str = "litserve-model"
    ) -> str:
        import litserve as ls
        from litserve import docker_builder

        console = self._console
        if os.path.exists("Dockerfile"):
            console.print("Dockerfile already exists. Skipping generation.")
            return os.path.abspath("Dockerfile")

        requirements = ""
        if os.path.exists("requirements.txt"):
            requirements = "-r requirements.txt"
        else:
            warnings.warn(
                f"requirements.txt not found at {os.getcwd()}. "
                f"Make sure to install the required packages in the Dockerfile.",
                UserWarning,
            )
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

    def generate_client(self) -> None:
        console = self._console
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

    def _build_container(self, path: str, repository: str, tag: str, console: Console, progress: Progress) -> None:
        build_task = progress.add_task("Building Docker image", total=None)
        build_status = self.client.api.build(
            path=os.path.dirname(path), dockerfile=path, tag=f"{repository}:{tag}", decode=True, quiet=False
        )
        for line in build_status:
            if "error" in line:
                progress.stop()
                console.print(f"\n[red]{line}[/red]")
                return
            if "stream" in line and line["stream"].strip():
                console.print(line["stream"].strip(), style="bright_black")
                progress.update(build_task, description="Building Docker image")

        progress.update(build_task, description="[green]Build completed![/green]")

    def _push_container(
        self, repository: str, tag: str, teamspace: Teamspace, lit_cr: LitContainerApi, progress: Progress
    ) -> None:
        console = self._console
        push_task = progress.add_task("Pushing to registry", total=None)
        console.print("\nPushing image...", style="bold blue")
        lit_cr.authenticate()
        push_status = lit_cr.upload_container(repository, teamspace, tag=tag)
        for line in push_status:
            if "error" in line:
                progress.stop()
                console.print(f"\n[red]{line}[/red]")
                return
            if "status" in line:
                console.print(line["status"], style="bright_black")
                progress.update(push_task, description="Pushing to registry")
        progress.update(push_task, description="[green]Push completed![/green]")
