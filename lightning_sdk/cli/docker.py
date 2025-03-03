import os
import warnings
from pathlib import Path

import click
from rich.console import Console


@click.group(name="dockerize")
def dockerize() -> None:
    """Generate a Dockerfile for a LitServe model."""


@dockerize.command("api")
@click.argument("server-filename")
@click.option("--port", type=int, default=8000, help="Port to expose in the Docker container.")
@click.option("--gpu", is_flag=True, default=False, flag_value=True, help="Use a GPU-enabled Docker image.")
@click.option("--tag", default="litserve-model", help="Docker image tag to use in examples.")
def api(server_filename: str, port: int = 8000, gpu: bool = False, tag: str = "litserve-model") -> None:
    """Generate a Dockerfile for the given server code."""
    _api(server_filename=server_filename, port=port, gpu=gpu, tag=tag)


def _api(server_filename: str, port: int = 8000, gpu: bool = False, tag: str = "litserve-model") -> str:
    console = Console()

    if os.path.exists("Dockerfile"):
        console.print("Dockerfile already exists. Skipping generation.")
        return os.path.abspath("Dockerfile")

    import litserve as ls
    from litserve import docker_builder

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
