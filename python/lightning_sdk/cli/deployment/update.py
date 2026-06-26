"""Deployment update command."""

from typing import Optional, Sequence

import rich_click as click

from lightning_sdk.cli.deployment.common import (
    MACHINE_VALUES,
    build_release_strategy,
    parse_auth,
    parse_env,
    parse_path_mappings,
    parse_ports,
    resolve_machine,
    resolve_teamspace,
)
from lightning_sdk.cli.utils.cloud_selection import warn_deprecated_cloud_options
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.deployment import Deployment


@click.command("update", cls=LightningCommand)
@click.argument("name")
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace).")
@click.option("--new-name", help="Rename the deployment.")
@click.option("--image", help="New docker image.")
@click.option("--machine", type=click.Choice(MACHINE_VALUES), help="New machine type for replicas.")
@click.option("--command", help="New container command.")
@click.option("--entrypoint", help="New container entrypoint.")
@click.option("--replicas", type=int, help="New fixed replica count.")
@click.option("--min-replicas", type=int, help="New minimum autoscaling replicas.")
@click.option("--max-replicas", type=int, help="New maximum autoscaling replicas.")
@click.option("--port", "ports", multiple=True, type=float, help="Replacement exposed port. Can be repeated.")
@click.option("--cloud", help="New cloud provider or cloud account to run replicas on.")
@click.option(
    "--cloud-account", "--cloud_account", help="Deprecated. Use --cloud. New cloud account to run replicas on."
)
@click.option("--env", "-e", multiple=True, default=[""], help="Replacement env var in KEY=VALUE or JSON format.")
@click.option("--secret", multiple=True, help="Replacement secret name to expose as an environment variable.")
@click.option("--interruptible/--no-interruptible", default=None, help="Whether to use interruptible instances.")
@click.option("--quantity", type=int, help="New number of machines per replica.")
@click.option("--include-credentials/--no-include-credentials", default=None, help="Inject SDK credentials.")
@click.option("--custom-domain", help="New custom domain.")
@click.option("--api-key-auth", is_flag=True, default=False, help="Require Lightning API key auth on the endpoint.")
@click.option("--basic-auth", help="Require basic auth on the endpoint, in USERNAME:PASSWORD format.")
@click.option("--token-auth", help="Require bearer token auth on the endpoint.")
@click.option(
    "--path-mapping",
    "--path_mapping",
    multiple=True,
    default=[""],
    help="Replacement path mapping. Can be repeated.",
)
@click.option("--path-mappings", "--path_mappings", default="", help="Comma-separated replacement path mappings.")
@click.option("--max-runtime", type=int, help="New maximum machine allocation duration in seconds.")
@click.option("--max-surge", type=int, default=1, show_default=True, help="Rolling update max surge.")
@click.option("--max-unavailable", type=int, default=0, show_default=True, help="Rolling update max unavailable.")
def update_deployment(
    name: str,
    teamspace: Optional[str] = None,
    new_name: Optional[str] = None,
    image: Optional[str] = None,
    machine: Optional[str] = None,
    command: Optional[str] = None,
    entrypoint: Optional[str] = None,
    replicas: Optional[int] = None,
    min_replicas: Optional[int] = None,
    max_replicas: Optional[int] = None,
    ports: Sequence[float] = (),
    cloud: Optional[str] = None,
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
    max_surge: int = 1,
    max_unavailable: int = 0,
) -> None:
    """Update a deployment."""
    resolved_teamspace = resolve_teamspace(teamspace)
    warn_deprecated_cloud_options(cloud_account=cloud_account)
    env_vars = parse_env(env, secret)
    path_mappings_dict = parse_path_mappings(path_mapping, path_mappings)
    machine_obj = resolve_machine(machine)

    requested = [
        new_name,
        image,
        machine,
        command,
        entrypoint,
        replicas,
        min_replicas,
        max_replicas,
        cloud,
        cloud_account,
        env_vars,
        interruptible,
        quantity,
        include_credentials,
        custom_domain,
        api_key_auth or basic_auth or token_auth,
        path_mappings_dict,
        max_runtime,
    ]
    if not any(value is not None and value != {} for value in requested) and not ports:
        raise click.UsageError("No updates requested.")

    release_changes = any(
        value is not None and value != {}
        for value in [
            image,
            machine,
            command,
            entrypoint,
            cloud,
            cloud_account,
            env_vars,
            interruptible,
            quantity,
            include_credentials,
            path_mappings_dict,
            max_runtime,
        ]
    )

    deployment = Deployment(name=name, teamspace=resolved_teamspace)
    if not deployment.is_started:
        raise click.ClickException(f"Deployment {name!r} was not found.")
    deployment.update(
        machine=machine_obj,
        image=image,
        entrypoint=entrypoint,
        command=command,
        env=env_vars,
        spot=interruptible,
        cloud=cloud,
        cloud_account=cloud_account,
        min_replicas=min_replicas,
        max_replicas=max_replicas,
        name=new_name,
        ports=parse_ports(ports),
        release_strategy=build_release_strategy(max_surge, max_unavailable) if release_changes else None,
        replicas=replicas,
        auth=parse_auth(api_key_auth=api_key_auth, basic_auth=basic_auth, token_auth=token_auth),
        custom_domain=custom_domain,
        quantity=quantity,
        include_credentials=include_credentials,
        max_runtime=max_runtime,
        path_mappings=path_mappings_dict or None,
    )
    click.echo(f"Updated deployment {deployment.name}.")
