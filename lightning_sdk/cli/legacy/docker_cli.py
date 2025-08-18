import click

from lightning_sdk.serve import _LitServeDeployer


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
    return _LitServeDeployer(None, None).dockerize_api(server_filename=server_filename, port=port, gpu=gpu, tag=tag)
