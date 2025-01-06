import os
import subprocess
import warnings
from pathlib import Path
from typing import Union

from rich.console import Console


class _LitServe:
    """Serve a LitServe model.

    Example:
        lightning serve api server.py
    """

    def api(
        self,
        script_path: Union[str, Path],
        easy: bool = False,
    ) -> None:
        """Deploy a LitServe model script.

        Args:
            script_path: Path to the script to serve
            easy: If True, generates a client for the model

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

        try:
            subprocess.run(
                ["python", str(script_path)],
                check=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            error_msg = f"Script execution failed with exit code {e.returncode}\nstdout: {e.stdout}\nstderr: {e.stderr}"
            raise RuntimeError(error_msg) from None


class _Docker:
    """Generate a Dockerfile for a LitServe model."""

    def api(self, server_filename: str, port: int = 8000, gpu: bool = False) -> None:
        """Generate a Dockerfile for the given server code.

        Example:
            lightning litserve dockerize server.py --port 8000 --gpu

        Args:
            server_filename (str): The path to the server file. Example sever.py or app.py.
            port (int, optional): The port to expose in the Docker container.
            gpu (bool, optional): Whether to use a GPU-enabled Docker image.
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
            run_cmd = f"docker run --gpus all -p {port}:{port} litserve-model:latest"
            docker_template = docker_builder.CUDA_DOCKER_TEMPLATE
        else:
            run_cmd = f"docker run -p {port}:{port} litserve-model:latest"
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
> [underline]docker build -t litserve-model .[/underline]

[bold]To run the Docker container on the machine:[/bold]
> [underline]{run_cmd}[/underline]

[bold]To push the container to a registry:[/bold]
> [underline]docker push litserve-model[/underline]
"""
        console.print(success_msg)
