"""Deployment create command."""

from typing import Optional, Sequence

import click

from lightning_sdk.cli.deployment.common import (
    MACHINE_VALUES,
    build_autoscale,
    parse_auth,
    parse_env,
    parse_path_mappings,
    parse_ports,
    resolve_machine,
    resolve_teamspace,
)
from lightning_sdk.deployment import Deployment


@click.command("create")
@click.argument("name", required=False)
@click.option("--name", "name_option", help="The deployment name. Overrides the optional NAME argument.")
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace).")
@click.option("--image", help="Docker image to deploy. Mutually exclusive with --studio.")
@click.option("--studio", help="Studio to deploy from. Mutually exclusive with --image.")
@click.option(
    "--machine",
    default="CPU",
    show_default=True,
    type=click.Choice(MACHINE_VALUES),
    help="The machine type to run replicas on.",
)
@click.option("--port", "ports", multiple=True, type=float, required=True, help="Port to expose. Can be repeated.")
@click.option("--command", help="Container command.")
@click.option("--entrypoint", help="Container entrypoint. Omit to use the image default.")
@click.option("--replicas", type=int, help="Fixed number of replicas to start.")
@click.option("--min-replicas", type=int, help="Minimum autoscaling replicas.")
@click.option("--max-replicas", type=int, help="Maximum autoscaling replicas.")
@click.option("--autoscale-metric", type=click.Choice(["CPU", "GPU", "RPM"]), help="Autoscaling metric.")
@click.option("--autoscale-threshold", type=float, help="Autoscaling threshold.")
@click.option("--cloud-account", "--cloud_account", help="Cloud account to run replicas on.")
@click.option("--env", "-e", multiple=True, default=[""], help="Environment variable in KEY=VALUE or JSON format.")
@click.option("--secret", multiple=True, help="Secret name to expose as an environment variable.")
@click.option("--interruptible/--no-interruptible", default=None, help="Whether to use interruptible instances.")
@click.option("--quantity", type=int, help="Number of machines per replica.")
@click.option("--include-credentials/--no-include-credentials", default=None, help="Inject SDK credentials.")
@click.option("--custom-domain", help="Custom domain to attach to the deployment.")
@click.option("--api-key-auth", is_flag=True, default=False, help="Require Lightning API key auth on the endpoint.")
@click.option("--basic-auth", help="Require basic auth on the endpoint, in USERNAME:PASSWORD format.")
@click.option("--token-auth", help="Require bearer token auth on the endpoint.")
@click.option(
    "--path-mapping",
    "--path_mapping",
    multiple=True,
    default=[""],
    help="Map a container path to a data connection path. Can be repeated.",
)
@click.option("--path-mappings", "--path_mappings", default="", help="Comma-separated path mappings.")
@click.option("--max-runtime", type=int, help="Maximum machine allocation duration in seconds.")
def create_deployment(
    name: Optional[str] = None,
    name_option: Optional[str] = None,
    teamspace: Optional[str] = None,
    image: Optional[str] = None,
    studio: Optional[str] = None,
    machine: str = "CPU",
    ports: Sequence[float] = (),
    command: Optional[str] = None,
    entrypoint: Optional[str] = None,
    replicas: Optional[int] = None,
    min_replicas: Optional[int] = None,
    max_replicas: Optional[int] = None,
    autoscale_metric: Optional[str] = None,
    autoscale_threshold: Optional[float] = None,
    cloud_account: Optional[str] = None,
    env: Sequence[str] = (),
    secret: Sequence[str] = (),
    interruptible: Optional[bool] = None,
    quantity: Optional[int] = None,
    include_credentials: Optional[bool] = None,
    custom_domain: Optional[str] = None,
    api_key_auth: bool = False,
    basic_auth: Optional[str] = None,
    token_auth: Optional[str] = None,
    path_mapping: Sequence[str] = (),
    path_mappings: str = "",
    max_runtime: Optional[int] = None,
) -> None:
    """Create a deployment."""
    deployment_name = name_option or name
    if not deployment_name:
        raise click.UsageError("Deployment name is required.")
    if image and studio:
        raise click.UsageError("--image and --studio are mutually exclusive.")
    if not image and not studio:
        raise click.UsageError("Either --image or --studio is required.")

    resolved_teamspace = resolve_teamspace(teamspace)
    machine_obj = resolve_machine(machine)
    deployment = Deployment(name=deployment_name, teamspace=resolved_teamspace)
    deployment.start(
        studio=studio,
        machine=machine_obj,
        image=image,
        autoscale=build_autoscale(
            machine_obj,
            replicas,
            min_replicas,
            max_replicas,
            autoscale_metric,
            autoscale_threshold,
        ),
        ports=parse_ports(ports),
        entrypoint=entrypoint,
        command=command,
        env=parse_env(env, secret),
        spot=interruptible,
        replicas=replicas,
        auth=parse_auth(api_key_auth=api_key_auth, basic_auth=basic_auth, token_auth=token_auth),
        cloud_account=cloud_account,
        custom_domain=custom_domain,
        quantity=quantity,
        include_credentials=include_credentials,
        max_runtime=max_runtime,
        path_mappings=parse_path_mappings(path_mapping, path_mappings),
    )
    click.echo(f"Created deployment {deployment.name}.")
