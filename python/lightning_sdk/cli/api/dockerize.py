"""API dockerize command."""

import rich_click as click

from lightning_sdk.cli.legacy.docker_cli import _api
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("dockerize", cls=LightningCommand)
@click.argument("server_filename")
@click.option("--port", type=int, default=8000, help="Port to expose in the Docker container.")
@click.option("--gpu", is_flag=True, default=False, flag_value=True, help="Use a GPU-enabled Docker image.")
@click.option("--tag", default="litserve-model", help="Docker image tag to use in examples.")
def dockerize_api(server_filename: str, port: int = 8000, gpu: bool = False, tag: str = "litserve-model") -> None:
    """Generate a Dockerfile for the given server code."""
    _api(server_filename=server_filename, port=port, gpu=gpu, tag=tag)
