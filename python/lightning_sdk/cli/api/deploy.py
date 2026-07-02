"""API deploy command."""

from typing import Any

import rich_click as click

from lightning_sdk.cli.legacy.deploy.serve import api_impl
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("deploy", cls=LightningCommand)
@click.argument("script_path")
@click.option("--easy", is_flag=True, default=False, help="Generate a client for the model")
@click.option(
    "--cloud",
    is_flag=False,
    flag_value="",
    type=str,
    help="Run the model on cloud, optionally selecting a cloud provider or cloud account.",
)
@click.option("--name", default=None, help="Name of the deployed API (e.g., 'classification-api', 'Llama-api')")
@click.option(
    "--non-interactive", "--non_interactive", is_flag=True, default=False, help="Do not prompt for confirmation"
)
@click.option("--machine", default="CPU", help="Machine type to deploy the API on. Defaults to CPU.")
@click.option(
    "--devbox",
    default=None,
    help="Machine type to build the API on. Setting this argument will open the server in a Studio.",
)
@click.option(
    "--interruptible", is_flag=True, default=False, help="Whether the machine should be interruptible (spot) or not."
)
@click.option(
    "--teamspace",
    default=None,
    help="The teamspace the deployment should be associated with. Defaults to the current teamspace.",
)
@click.option(
    "--org", default=None, help="The organization owning the teamspace (if any). Defaults to the current organization."
)
@click.option("--user", default=None, help="The user owning the teamspace (if any). Defaults to the current user.")
@click.option("--port", default=None, type=int, help="The port to expose the API on.")
@click.option("--min_replica", "--min-replica", default=None, type=int, help="Number of replicas to start with.")
@click.option("--max_replica", "--max-replica", default=None, type=int, help="Number of replicas to scale up to.")
@click.option("--replicas", default=None, type=int, help="Deployment will start with this many replicas.")
@click.option(
    "--no_credentials",
    "--no-credentials",
    is_flag=True,
    default=False,
    help="Whether to include credentials in the deployment.",
)
def deploy_api(**kwargs: Any) -> None:
    """Deploy a LitServe model script."""
    kwargs["include_credentials"] = not kwargs.pop("no_credentials")
    api_impl(**kwargs)
