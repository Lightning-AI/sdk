import os
import shlex
import subprocess
from pathlib import Path
from typing import Generator, List, Optional, Union

import docker
from rich.console import Console

from lightning_sdk import Deployment, Machine, Teamspace
from lightning_sdk.api.deployment_api import AutoScaleConfig, DeploymentApi, Env, Secret
from lightning_sdk.api.lit_container_api import LitContainerApi
from lightning_sdk.api.utils import _get_cloud_url
from lightning_sdk.lightning_cloud.env import LIGHTNING_CLOUD_URL

_DOCKER_NOT_RUNNING_MSG = (
    "Deploying LitServe requires Docker to be running on the machine. "
    "If Docker is not installed, please install it from https://docs.docker.com/get-docker/ "
    "and start the Docker daemon before running this command."
)


class _LitServeDeployer:
    def __init__(self, name: Optional[str], teamspace: Optional[Teamspace]) -> None:
        self.name = name
        self.teamspace = teamspace
        self._console = Console()
        self._client = None

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

    @property
    def created(self) -> bool:
        return DeploymentApi().get_deployment_by_name(self.name, self.teamspace.id) is not None

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

Check out [blue][link=https://lightning.ai/docs/litserve/features]the docs[/link][/blue] for more details.
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

    def build_container(self, path: str, repository: str, tag: str) -> Generator[str, None, None]:
        build_logs = self._docker_build_with_logs(path, repository, tag=tag)

        for line in build_logs:
            if "error" in line:
                raise RuntimeError(f"Failed to build image: {line}")
            else:
                yield line.strip()

    def push_container(
        self,
        repository: str,
        tag: str,
        teamspace: Teamspace,
        lit_cr: LitContainerApi,
        cloud_account: str,
    ) -> Generator[dict, None, dict]:
        lit_cr.authenticate()
        push_status = lit_cr.upload_container(
            repository, teamspace, tag=tag, cloud_account=cloud_account, platform=None
        )
        for line in push_status:
            if "error" in line:
                raise RuntimeError(f"Failed to push image: {line}")
            if "status" in line:
                yield {"status": line["status"].strip()}

        container_basename = repository.split("/")[-1]
        repository = lit_cr.get_container_url(repository, tag, teamspace, cloud_account)

        yield {
            "finish": True,
            "status": "Container pushed successfully",
            "url": f"{LIGHTNING_CLOUD_URL}/{teamspace.owner.name}/{teamspace.name}/containers/{container_basename}"
            f"{f'?clusterId={cloud_account}' if cloud_account is not None else ''}",
            "image": repository,
        }

    def _update_deployment(
        self,
        deployment: Deployment,
        machine: Optional[Machine] = None,
        image: Optional[str] = None,
        entrypoint: Optional[str] = None,
        command: Optional[str] = None,
        env: Optional[List[Union[Env, Secret]]] = None,
        min_replica: Optional[int] = 0,
        max_replica: Optional[int] = 1,
        spot: Optional[bool] = None,
        replicas: Optional[int] = 1,
        cloud_account: Optional[str] = None,
        port: Optional[int] = 8000,
        include_credentials: Optional[bool] = True,
    ) -> None:
        return deployment.update(
            machine=machine,
            image=image,
            entrypoint=entrypoint,
            command=command,
            env=env,
            max_replicas=max_replica,
            min_replicas=min_replica,
            replicas=replicas,
            spot=spot,
            cloud_account=cloud_account,
            ports=[port],
            include_credentials=include_credentials,
        )

    def run_on_cloud(
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
        cloudspace_id: Optional[str] = None,
        from_onboarding: bool = False,
    ) -> dict:
        """Run a deployment on the cloud. If the deployment already exists, it will be updated.

        Args:
            deployment_name: The name of the deployment.
            teamspace: The teamspace to run the deployment on.
            image: The image to run the deployment on.
            metric: The metric to use for autoscaling. Defaults to None.
            machine: The machine to run the deployment on. Defaults to None.
            min_replica: The minimum number of replicas to run. Defaults to 0.
            max_replica: The maximum number of replicas to run. Defaults to 1.
            spot: Whether to run the deployment on spot instances. Defaults to None.
            replicas: The number of replicas to run. Defaults to 1.
            cloud_account: The cloud account to run the deployment on. Defaults to None.
            port: The port to run the deployment on. Defaults to 8000.
            include_credentials: Whether to include credentials in the deployment. Defaults to True.
            cloudspace_id: Connect to a Studio.
            from_onboarding: Deployment created during onboarding.

        Returns:
            dict: The deployment and the URL of the deployment.
        """
        url = f"{_get_cloud_url()}/{teamspace.owner.name}/{teamspace.name}/jobs/{deployment_name}"
        machine = machine or Machine.CPU
        metric = metric or ("CPU" if machine.is_cpu() else "GPU")
        deployment = Deployment(deployment_name, teamspace)
        if deployment.is_started:
            self._console.print(f"Deployment with name {deployment_name} already running. Updating the deployment.")
            self._update_deployment(
                deployment,
                machine,
                image,
                min_replica=min_replica,
                max_replica=max_replica,
                spot=spot,
                replicas=replicas,
                cloud_account=cloud_account,
                port=port,
                include_credentials=include_credentials,
            )
            return {"deployment": deployment, "url": url, "updated": True}
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
            cloudspace_id=cloudspace_id,
            from_litserve=True,
            from_onboarding=from_onboarding,
            command="",
        )

        return {"deployment": deployment, "url": url}
