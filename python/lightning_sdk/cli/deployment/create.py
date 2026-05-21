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
@click.option("--port", "ports", multiple=True, type=float, help="Port to expose. Can be repeated.")
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
@click.option("--model", help="HuggingFace model id to serve (BYOM). Mutually exclusive with --image/--studio.")
@click.option(
    "--hf-token-secret",
    help="Name of the Lightning secret holding your HuggingFace token (gated/private models).",
)
@click.option("--byom-image-variant", "base_image_variant", help="vLLM serving image variant. Defaults to 'stable'.")
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
    model: Optional[str] = None,
    hf_token_secret: Optional[str] = None,
    base_image_variant: Optional[str] = None,
    tensor_parallel_size: Optional[int] = None,
    max_model_len: Optional[int] = None,
    gpu_memory_utilization: Optional[float] = None,
    quantization: Optional[str] = None,
    dtype: Optional[str] = None,
    extra_vllm_args: Sequence[str] = (),
) -> None:
    """Create a deployment."""
    deployment_name = name_option or name
    if not deployment_name:
        raise click.UsageError("Deployment name is required.")
    if sum([bool(image), bool(studio), bool(model)]) != 1:
        raise click.UsageError("Exactly one of --image, --studio, or --model is required.")

    resolved_teamspace = resolve_teamspace(teamspace)
    machine_obj = resolve_machine(machine)

    if model:
        if machine_obj is None or machine_obj.is_cpu():
            raise click.UsageError("BYOM (--model) requires a GPU machine; pass --machine (e.g. L4, A100).")
        if not ports:
            ports = (8000.0,)
    elif not ports:
        raise click.UsageError("--port is required.")

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
        model=model,
        hf_token_secret=hf_token_secret,
        base_image_variant=base_image_variant,
        tensor_parallel_size=tensor_parallel_size,
        max_model_len=max_model_len,
        gpu_memory_utilization=gpu_memory_utilization,
        quantization=quantization,
        dtype=dtype,
        extra_vllm_args=list(extra_vllm_args) or None,
    )
    click.echo(f"Created deployment {deployment.name}.")
