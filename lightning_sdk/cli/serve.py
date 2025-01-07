import os
import subprocess
import warnings
from pathlib import Path
from typing import Optional, Union

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm


class _LitServe:
    """Serve a LitServe model.

    Example:
        lightning serve api server.py  # serve locally
        lightning serve api server.py --cloud  # deploy to the cloud

    You can deploy the API to the cloud by running `lightning serve api server.py --cloud`.
    This will generate a Dockerfile, build the image, and push it to the image registry.
    Deploying to the cloud requires pre-login to the docker registry.
    """

    def api(
        self,
        script_path: Union[str, Path],
        easy: bool = False,
        cloud: bool = False,
        repository: Optional[str] = None,
        non_interactive: bool = False,
    ) -> None:
        """Deploy a LitServe model script.

        Args:
            script_path: Path to the script to serve
            easy: If True, generates a client for the model
            cloud: If True, deploy the model to the Lightning Studio
            repository: Optional Docker repository name (e.g., 'username/model-name')
            non_interactive: If True, do not prompt for confirmation
        Raises:
            FileNotFoundError: If script_path doesn't exist
            ImportError: If litserve is not installed
            subprocess.CalledProcessError: If the script fails to run
            IOError: If client.py generation fails
        """
        console = Console()
        script_path = Path(script_path)
        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")
        if not script_path.is_file():
            raise ValueError(f"Path is not a file: {script_path}")

        try:
            from litserve.python_client import client_template
        except ImportError:
            raise ImportError(
                "litserve is not installed. Please install it with `pip install lightning_sdk[serve]`"
            ) from None

        if easy:
            client_path = Path("client.py")
            if client_path.exists():
                console.print("Skipping client generation: client.py already exists", style="blue")
            else:
                try:
                    client_path.write_text(client_template)
                    console.print("✅ Client generated at client.py", style="bold green")
                except OSError as e:
                    raise OSError(f"Failed to generate client.py: {e!s}") from None

        if cloud:
            tag = repository if repository else "litserve-model"
            return self._handle_cloud(script_path, console, tag=tag, non_interactive=non_interactive)

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
        self,
        script_path: Union[str, Path],
        console: Console,
        tag: str = "litserve-model",
        non_interactive: bool = False,
    ) -> None:
        try:
            import docker
        except ImportError:
            raise ImportError("docker-py is not installed. Please install it with `pip install docker`") from None

        try:
            client = docker.from_env()
            client.ping()
        except docker.errors.DockerException as e:
            raise RuntimeError(f"Failed to connect to Docker daemon: {e!s}. Is Docker running?") from None

        dockerizer = _Docker()
        path = dockerizer.api(script_path, port=8000, gpu=False, tag=tag)

        console.clear()
        if non_interactive:
            console.print("[italic]non-interactive[/italic] mode enabled, skipping confirmation prompts", style="blue")

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
            transient=False,
        ) as progress:
            build_task = progress.add_task("Building Docker image", total=None)
            build_status = client.api.build(
                path=os.path.dirname(path), dockerfile=path, tag=tag, decode=True, quiet=False
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

            push_task = progress.add_task("Pushing to registry", total=None)
            console.print("\nPushing image...", style="bold blue")
            push_status = client.api.push(tag, stream=True, decode=True)
            for line in push_status:
                if "error" in line:
                    progress.stop()
                    console.print(f"\n[red]{line}[/red]")
                    return
                if "status" in line:
                    console.print(line["status"], style="bright_black")
                    progress.update(push_task, description="Pushing to registry")

            progress.update(push_task, description="[green]Push completed![/green]")

        console.print(f"\n✅ Image pushed to {tag}", style="bold green")
        console.print(
            "Soon you will be able to deploy this model to the Lightning Studio!",
        )
        # TODO: Deploy to the cloud


class _Docker:
    """Generate a Dockerfile for a LitServe model."""

    def api(self, server_filename: str, port: int = 8000, gpu: bool = False, tag: str = "litserve-model") -> str:
        """Generate a Dockerfile for the given server code.

        Args:
            server_filename: The path to the server file. Example sever.py or app.py.
            port: The port to expose in the Docker container.
            gpu: Whether to use a GPU-enabled Docker image.
            tag: Docker image tag to use in examples.
        """
        import litserve as ls
        from litserve import docker_builder

        console = Console()
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
