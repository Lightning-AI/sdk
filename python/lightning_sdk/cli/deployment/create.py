"""Deployment create command."""

import json
import sys
from typing import List, Optional, Sequence

import click

from lightning_sdk.api.deployment_api import to_byom_spec
from lightning_sdk.cli.deployment._byom_ack import create_with_acknowledgement
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
from lightning_sdk.cli.utils.cloud_selection import warn_deprecated_cloud_options
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
@click.option("--port", "ports", multiple=True, type=float, help="Port to expose. Can be repeated.")
@click.option("--command", help="Container command.")
@click.option("--entrypoint", help="Container entrypoint. Omit to use the image default.")
@click.option("--replicas", type=int, help="Fixed number of replicas to start.")
@click.option("--min-replicas", type=int, help="Minimum autoscaling replicas.")
@click.option("--max-replicas", type=int, help="Maximum autoscaling replicas.")
@click.option("--autoscale-metric", type=click.Choice(["CPU", "GPU", "RPM"]), help="Autoscaling metric.")
@click.option("--autoscale-threshold", type=float, help="Autoscaling threshold.")
@click.option("--cloud", help="Cloud provider or cloud account to run replicas on.")
@click.option("--cloud-account", "--cloud_account", help="Deprecated. Use --cloud. Cloud account to run replicas on.")
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
@click.option("--model", help="HuggingFace model id to serve. Mutually exclusive with --image/--studio.")
@click.option(
    "--hf-token-secret",
    help="Name of the Lightning secret holding your HuggingFace token (gated/private models).",
)
@click.option("--serving-image-variant", "base_image_variant", help="vLLM serving image variant. Defaults to 'stable'.")
@click.option("--tensor-parallel-size", type=int, help="vLLM tensor-parallel size.")
@click.option("--max-model-len", type=int, help="Maximum model context length.")
@click.option("--gpu-memory-utilization", type=float, help="Fraction of GPU memory vLLM may use (0-1).")
@click.option("--quantization", help="Quantization method (e.g. fp8, awq).")
@click.option("--dtype", help="Model weight dtype (e.g. bfloat16).")
@click.option(
    "--vllm-arg",
    "extra_vllm_args",
    multiple=True,
    help="Extra raw vLLM arg, repeatable (e.g. --vllm-arg --enable-chunked-prefill).",
)
@click.option(
    "--enable-weight-reload/--no-enable-weight-reload",
    "enable_weight_reload",
    default=None,
    help="Enable hot weight reload (HuggingFace auto-detect + user-triggered) without redeploying.",
)
@click.option("--ack", "acks", multiple=True, help="Acknowledge a model validation warning by code (repeatable).")
@click.option(
    "--force", is_flag=True, default=False, help="Acknowledge all model validation warnings and deploy anyway."
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print the resolved model configuration without creating the deployment.",
)
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
    model: Optional[str] = None,
    hf_token_secret: Optional[str] = None,
    base_image_variant: Optional[str] = None,
    tensor_parallel_size: Optional[int] = None,
    max_model_len: Optional[int] = None,
    gpu_memory_utilization: Optional[float] = None,
    quantization: Optional[str] = None,
    dtype: Optional[str] = None,
    extra_vllm_args: Sequence[str] = (),
    enable_weight_reload: Optional[bool] = None,
    acks: Sequence[str] = (),
    force: bool = False,
    dry_run: bool = False,
) -> None:
    """Create a deployment."""
    deployment_name = name_option or name
    if not deployment_name:
        raise click.UsageError("Deployment name is required.")
    if sum([bool(image), bool(studio), bool(model)]) != 1:
        raise click.UsageError("Exactly one of --image, --studio, or --model is required.")
    if (acks or force or dry_run) and not model:
        raise click.UsageError("--ack, --force, and --dry-run are only supported with --model.")

    resolved_teamspace = resolve_teamspace(teamspace)
    warn_deprecated_cloud_options(cloud_account=cloud_account)
    machine_obj = resolve_machine(machine)
    vllm_args = list(extra_vllm_args) or None

    if model:
        if machine_obj is None or machine_obj.is_cpu():
            raise click.UsageError("Serving a model (--model) requires a GPU machine; pass --machine (e.g. L4, A100).")
        if not ports:
            ports = (8000.0,)
    elif not ports:
        raise click.UsageError("--port is required.")

    if dry_run:
        spec = to_byom_spec(
            model,
            hf_token_secret=hf_token_secret,
            base_image_variant=base_image_variant,
            tensor_parallel_size=tensor_parallel_size,
            max_model_len=max_model_len,
            gpu_memory_utilization=gpu_memory_utilization,
            quantization=quantization,
            dtype=dtype,
            extra_vllm_args=vllm_args,
            enable_weight_reload=enable_weight_reload,
        )
        click.echo("Dry run — model configuration that would be deployed:")
        click.echo(json.dumps({k: v for k, v in spec.to_dict().items() if v is not None}, indent=2, sort_keys=True))
        click.echo("No deployment created.")
        return

    def _create(acknowledged: List[str]) -> Deployment:
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
            cloud=cloud,
            cloud_account=cloud_account,
            custom_domain=custom_domain,
            quantity=quantity,
            include_credentials=include_credentials,
            max_runtime=max_runtime,
            path_mappings=parse_path_mappings(path_mapping, path_mappings),
            model=model,
            hf_token_secret=hf_token_secret,
            base_image_variant=base_image_variant,
            tensor_parallel_size=tensor_parallel_size,
            max_model_len=max_model_len,
            gpu_memory_utilization=gpu_memory_utilization,
            quantization=quantization,
            dtype=dtype,
            extra_vllm_args=vllm_args,
            enable_weight_reload=enable_weight_reload,
            acknowledged_warnings=acknowledged or None,
        )
        return deployment

    deployment = create_with_acknowledgement(_create, acks=list(acks), force=force, interactive=sys.stdin.isatty())
    click.echo(f"Created deployment {deployment.name}.")
